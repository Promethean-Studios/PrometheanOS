import json
import shutil
import subprocess
from typing import Any, Dict, List

import psutil


class HardwareMonitor:
    """Collect hardware telemetry for the Promethean Control Center."""

    AI_PROCESS_NAMES = {
        "ollama",
        "llama",
        "llama.cpp",
        "python",
        "python3",
        "vllm",
        "jupyter",
        "transformers",
        "pytorch",
        "tensorrt",
        "nvidia-smi",
        "cuda",
    }

    @staticmethod
    def get_cpu_temp_c() -> float:
        temps = psutil.sensors_temperatures()
        if not temps:
            return 0.0

        readings: List[float] = []
        for entries in temps.values():
            for item in entries or []:
                if getattr(item, "current", None) is not None:
                    readings.append(float(item.current))

        if not readings:
            return 0.0

        return sum(readings) / len(readings)

    @staticmethod
    def get_vram_usage_mb() -> Dict[str, float]:
        if shutil.which("nvidia-smi"):
            try:
                completed = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                output = completed.stdout.strip()
                if output:
                    parts = [p.strip() for p in output.split(",")]
                    if len(parts) >= 2:
                        used_mb = float(parts[0])
                        total_mb = float(parts[1])
                        return {
                            "used_mb": used_mb,
                            "total_mb": total_mb,
                            "usage_percent": (used_mb / total_mb * 100.0) if total_mb else 0.0,
                        }
            except (subprocess.CalledProcessError, ValueError):
                pass

        mem = psutil.virtual_memory()
        return {
            "used_mb": float(mem.used) / (1024 * 1024),
            "total_mb": float(mem.total) / (1024 * 1024),
            "usage_percent": mem.percent,
        }

    @staticmethod
    def detect_ai_workloads() -> List[Dict[str, Any]]:
        workloads: List[Dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            name = (info.get("name") or "").lower()
            cmdline = " ".join(info.get("cmdline") or []).lower()
            if not name and not cmdline:
                continue

            if not any(keyword in name or keyword in cmdline for keyword in HardwareMonitor.AI_PROCESS_NAMES):
                continue

            try:
                rss = info.get("memory_info")
                if isinstance(rss, dict):
                    memory_mb = float(rss.get("rss", 0)) / (1024 * 1024)
                else:
                    memory_mb = getattr(rss, "rss", 0) / (1024 * 1024) if rss else 0.0
            except Exception:
                memory_mb = 0.0

            workloads.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name") or "unknown",
                    "cmdline": info.get("cmdline") or [],
                    "memory_mb": memory_mb,
                }
            )

        return workloads

    @staticmethod
    def snapshot() -> Dict[str, Any]:
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        return {
            "cpu_percent": cpu,
            "memory": {
                "used_mb": round(float(memory.used) / (1024 * 1024), 2),
                "total_mb": round(float(memory.total) / (1024 * 1024), 2),
                "usage_percent": memory.percent,
            },
            "cpu_temp_c": HardwareMonitor.get_cpu_temp_c(),
            "vram": HardwareMonitor.get_vram_usage_mb(),
            "ai_workloads": HardwareMonitor.detect_ai_workloads(),
        }

    @staticmethod
    def to_json() -> str:
        return json.dumps(HardwareMonitor.snapshot(), indent=2, sort_keys=True)
