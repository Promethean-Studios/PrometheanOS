from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil


def _run(command: List[str], timeout: float = 2.0) -> Optional[subprocess.CompletedProcess[str]]:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _first_line(value: str) -> str:
    return next((line.strip() for line in value.splitlines() if line.strip()), "")


class HardwareProvider(ABC):
    """Base provider for read-only hardware metrics and capabilities."""

    @staticmethod
    @abstractmethod
    def detect() -> Dict[str, Any]:
        raise NotImplementedError


class CPUProvider(HardwareProvider):
    @staticmethod
    def _cpuinfo() -> Dict[str, str]:
        values: Dict[str, str] = {}
        try:
            for line in Path("/proc/cpuinfo").read_text(errors="replace").splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    values.setdefault(key.strip().lower(), value.strip())
        except OSError:
            pass
        return values

    @staticmethod
    def detect() -> Dict[str, Any]:
        info = CPUProvider._cpuinfo()
        frequency = psutil.cpu_freq()
        flags = info.get("flags", info.get("features", "")).split()
        temperatures = {}
        try:
            for name, entries in psutil.sensors_temperatures().items():
                temperatures[name] = [{"label": item.label, "current": item.current, "high": item.high, "critical": item.critical} for item in entries]
        except (AttributeError, OSError):
            pass
        readings = [item["current"] for entries in temperatures.values() for item in entries if item["current"] is not None]
        return {
            "vendor": info.get("vendor_id", "unknown"),
            "model": info.get("model name", platform.processor() or platform.machine()),
            "architecture": platform.machine(),
            "arch": platform.machine(),
            "logical_cores": psutil.cpu_count(logical=True) or 0,
            "physical_cores": psutil.cpu_count(logical=False),
            "cores": psutil.cpu_count(logical=True) or 0,
            "frequency_mhz": round(frequency.current, 2) if frequency else None,
            "supported_instruction_sets": sorted(set(flags)),
            "load_percent": psutil.cpu_percent(interval=None),
            "temperatures_c": temperatures,
            "temperature_c": round(sum(readings) / len(readings), 2) if readings else None,
        }


class GPUProvider(HardwareProvider):
    @staticmethod
    def _nvidia() -> Optional[Dict[str, Any]]:
        if not shutil.which("nvidia-smi"):
            return None
        result = _run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu,clocks.gr,power.draw,driver_version", "--format=csv,noheader,nounits"])
        if result is None or result.returncode != 0:
            return {"vendor": "nvidia", "status": "installed_but_broken", "runtime": {"cuda": "installed_but_broken"}}
        fields = [item.strip() for item in _first_line(result.stdout).split(",")]
        if len(fields) < 8:
            return {"vendor": "nvidia", "status": "installed_but_broken", "runtime": {"cuda": "installed_but_broken"}}

        def number(value: str) -> Optional[float]:
            return float(value) if value not in {"N/A", "[Not Supported]"} else None

        return {
            "vendor": "nvidia", "status": "available", "name": fields[0], "model": fields[0],
            "vram_mb": number(fields[1]), "vram_used_mb": number(fields[2]), "utilization_percent": number(fields[3]),
            "temperature_c": number(fields[4]), "clock_mhz": number(fields[5]), "power_w": number(fields[6]),
            "driver": fields[7], "runtime": {"cuda": "available"}, "family": "cuda-capable",
        }

    @staticmethod
    def _pci_gpu() -> Optional[Dict[str, Any]]:
        if not shutil.which("lspci"):
            return None
        result = _run(["lspci", "-nn"])
        output = "" if result is None else result.stdout
        gpu_lines = [line for line in output.splitlines() if re.search(r"(vga|3d controller|display controller)", line, re.I)]
        if not gpu_lines:
            return None
        line = gpu_lines[0]
        lower = line.lower()
        vendor, family = "unknown", "unsupported"
        if "amd" in lower or "radeon" in lower:
            vendor, family = "amd", "rocm-capable"
        elif "intel" in lower:
            vendor, family = "intel", "integrated"
        elif "nvidia" in lower:
            vendor, family = "nvidia", "cuda-capable"
        name = line.split(": ", 1)[-1]
        return {"vendor": vendor, "status": "available" if vendor != "unknown" else "unsupported", "name": name, "model": name, "family": family, "runtime": {}, "utilization_percent": None, "temperature_c": None, "clock_mhz": None, "power_w": None, "vram_mb": None, "vram_used_mb": None}

    @staticmethod
    def detect() -> Dict[str, Any]:
        nvidia = GPUProvider._nvidia()
        if nvidia:
            return nvidia
        pci = GPUProvider._pci_gpu()
        if pci:
            return pci
        return {"vendor": "none", "status": "unsupported", "name": "no-gpu", "model": None, "family": "cpu-only", "runtime": {}, "utilization_percent": None, "temperature_c": None, "clock_mhz": None, "power_w": None, "vram_mb": None, "vram_used_mb": None}


class StorageProvider(HardwareProvider):
    MODEL_PATHS = ("/data/models", "/data/models/huggingface", "/data/models/ollama", "/var/lib/ollama", "~/.cache/huggingface", "~/.cache/torch", "~/.ollama")

    @staticmethod
    def _mounts() -> List[Dict[str, Any]]:
        mounts, seen = [], set()
        for partition in psutil.disk_partitions(all=False):
            if partition.mountpoint in seen:
                continue
            seen.add(partition.mountpoint)
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except OSError:
                continue
            mounts.append({"device": partition.device, "filesystem": partition.fstype, "mount_point": partition.mountpoint, "capacity_gb": round(usage.total / 1024**3, 2), "available_gb": round(usage.free / 1024**3, 2), "used_gb": round(usage.used / 1024**3, 2), "percent_used": usage.percent, "activity": None})
        return mounts

    @staticmethod
    def detect() -> Dict[str, Any]:
        mounts = StorageProvider._mounts()
        if not any(item["mount_point"] == "/" for item in mounts):
            try:
                usage = psutil.disk_usage("/")
                mounts.append({"device": "", "filesystem": "", "mount_point": "/", "capacity_gb": round(usage.total / 1024**3, 2), "available_gb": round(usage.free / 1024**3, 2), "used_gb": round(usage.used / 1024**3, 2), "percent_used": usage.percent, "activity": None})
            except OSError:
                pass
        root = next((item for item in mounts if item["mount_point"] == "/"), None) or {"capacity_gb": 0, "used_gb": 0, "available_gb": 0, "percent_used": 0}
        locations = []
        for raw_path in StorageProvider.MODEL_PATHS:
            path = Path(raw_path).expanduser() if raw_path.startswith("~") else Path(raw_path)
            try:
                exists = path.is_dir()
                locations.append({"path": str(path), "exists": exists, "readable": os.access(path, os.R_OK) if exists else False})
            except OSError:
                locations.append({"path": str(path), "exists": False, "readable": False})
        try:
            io = psutil.disk_io_counters()
            activity = {"read_bytes": io.read_bytes, "write_bytes": io.write_bytes} if io else None
        except (AttributeError, OSError):
            activity = None
        for mount in mounts:
            mount["activity"] = activity
        return {"disks": mounts, "model_locations": locations, "total_gb": root["capacity_gb"], "used_gb": root["used_gb"], "free_gb": root["available_gb"], "percent_used": root["percent_used"]}


class NetworkProvider(HardwareProvider):
    @staticmethod
    def detect() -> Dict[str, Any]:
        addrs = psutil.net_if_addrs()
        counters = psutil.net_io_counters(pernic=True)
        interfaces = {}
        for key, values in addrs.items():
            counter = counters.get(key)
            interfaces[key] = {"addresses": [addr.address for addr in values], "active": bool(counter and (counter.bytes_sent or counter.bytes_recv)), "upload_bytes": counter.bytes_sent if counter else None, "download_bytes": counter.bytes_recv if counter else None}
        return {"interfaces": interfaces, "active_interfaces": [key for key, item in interfaces.items() if item["active"]]}


class MemoryProvider(HardwareProvider):
    @staticmethod
    def detect() -> Dict[str, Any]:
        mem, swap = psutil.virtual_memory(), psutil.swap_memory()
        return {"total_mb": round(mem.total / 1024**2, 2), "used_mb": round(mem.used / 1024**2, 2), "available_mb": round(mem.available / 1024**2, 2), "percent_used": mem.percent, "swap_total_mb": round(swap.total / 1024**2, 2), "swap_used_mb": round(swap.used / 1024**2, 2), "swap_free_mb": round(swap.free / 1024**2, 2), "swap_percent_used": swap.percent}
