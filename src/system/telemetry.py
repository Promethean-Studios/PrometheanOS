from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Dict, Iterable, Optional

import psutil

from src.system.hardware.capabilities import CapabilityEngine
from src.system.hardware.providers import CPUProvider, GPUProvider, MemoryProvider, NetworkProvider, PowerProvider, StorageProvider, SystemProvider


UNAVAILABLE = None


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_call(name: str, function: Callable[[], Dict[str, Any]]) -> tuple[Dict[str, Any], Optional[str]]:
    try:
        value = function()
        return value if isinstance(value, dict) else {}, None
    except Exception as exc:
        return {}, f"{name}: {type(exc).__name__}"


class AIWorkloadDetector:
    """Identify likely AI processes without changing process state."""

    _MARKERS = {
        "ollama": ("ollama",),
        "llama.cpp": ("llama-server", "llama-cli", "llama.cpp", "llama-cpp-python"),
        "vllm": ("vllm",),
        "comfyui": ("comfyui", "comfy ui"),
        "jupyter": ("jupyter", "ipykernel"),
        "pytorch": ("torchrun", "torch.distributed", "accelerate launch", "deepspeed"),
    }
    _MODEL_PATTERN = re.compile(r"(?:--model(?:-path)?|model_path|model=)\s*[=:/]?\s*([^\s,]+)", re.I)

    @classmethod
    def _classify(cls, name: str, cmdline: str) -> Optional[str]:
        text = f"{name} {cmdline}".lower()
        for workload, markers in cls._MARKERS.items():
            if any(marker in text for marker in markers):
                return workload
        if name in {"python", "python3"} and any(marker in text for marker in ("transformers", "diffusers", "stable diffusion", "comfy")):
            return "python-ai"
        return None

    @classmethod
    def detect(cls, process_iter: Callable[..., Iterable[Any]] = psutil.process_iter) -> Dict[str, Any]:
        workloads = []
        errors = []
        try:
            processes = process_iter(["pid", "name", "cmdline", "memory_info", "cpu_percent"])
        except Exception as exc:
            return {"workloads": [], "errors": [f"process enumeration: {type(exc).__name__}"]}

        for process in processes:
            try:
                info = process.info
                name = (info.get("name") or "").lower()
                command = " ".join(info.get("cmdline") or [])
                workload = cls._classify(name, command)
                if not workload:
                    continue
                memory = info.get("memory_info")
                rss = getattr(memory, "rss", 0) if memory is not None else 0
                if isinstance(memory, dict):
                    rss = memory.get("rss", 0)
                model_match = cls._MODEL_PATTERN.search(command)
                workloads.append({
                    "pid": info.get("pid"),
                    "name": info.get("name") or "unknown",
                    "workload": workload,
                    "command": info.get("cmdline") or [],
                    "model": model_match.group(1) if model_match else None,
                    "memory_mb": round(float(rss) / (1024 * 1024), 2),
                    "cpu_percent": info.get("cpu_percent"),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as exc:
                errors.append(f"process: {type(exc).__name__}")
        return {"workloads": workloads, "errors": errors}


class SystemTelemetryCollector:
    """Poll and cache read-only system telemetry with per-section degradation."""

    def __init__(self, poll_interval: float = 2.0, capability_engine: Optional[CapabilityEngine] = None):
        self.poll_interval = max(0.0, float(poll_interval))
        self.capability_engine = capability_engine or CapabilityEngine()
        self._cached: Optional[Dict[str, Any]] = None
        self._polled_at = 0.0
        self._lock = threading.Lock()
        self._network_previous: Optional[Dict[str, Any]] = None

    def snapshot(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            now = monotonic()
            if self._cached is not None and not force and now - self._polled_at < self.poll_interval:
                return self._cached

            errors: Dict[str, str] = {}
            sections: Dict[str, Dict[str, Any]] = {}
            providers = {
                "cpu": CPUProvider.detect,
                "gpu": GPUProvider.detect,
                "memory": MemoryProvider.detect,
                "storage": StorageProvider.detect,
                "network": NetworkProvider.detect,
                "power": PowerProvider.detect,
                "system": SystemProvider.detect,
            }
            for name, provider in providers.items():
                sections[name], error = _safe_call(name, provider)
                if error:
                    errors[name] = error
            self._add_network_rates(sections.get("network", {}), now)

            ai, ai_error = _safe_call("ai", self._ai_snapshot)
            if ai_error:
                errors["ai"] = ai_error
            capabilities, capability_error = _safe_call("capabilities", self.capability_engine.detect)
            if capability_error:
                errors["capabilities"] = capability_error

            snapshot = {
                "timestamp": _timestamp(),
                "poll_interval_seconds": self.poll_interval,
                **sections,
                "ai": ai,
                "capabilities": capabilities,
                "errors": errors,
            }
            self._cached = snapshot
            self._polled_at = now
            return snapshot

    def _add_network_rates(self, network: Dict[str, Any], polled_at: float) -> None:
        current = network.get("interfaces", {})
        previous = self._network_previous
        elapsed = polled_at - self._polled_at if previous is not None else 0
        for name, interface in current.items():
            old = previous.get(name, {}) if previous else {}
            interface["upload_bytes_per_second"] = self._rate(interface.get("upload_bytes"), old.get("upload_bytes"), elapsed)
            interface["download_bytes_per_second"] = self._rate(interface.get("download_bytes"), old.get("download_bytes"), elapsed)
        self._network_previous = {
            name: {"upload_bytes": item.get("upload_bytes"), "download_bytes": item.get("download_bytes")}
            for name, item in current.items()
        }

    @staticmethod
    def _rate(current: Any, previous: Any, elapsed: float) -> Optional[float]:
        if elapsed <= 0 or not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
            return None
        return round(max(0, current - previous) / elapsed, 1)

    def _ai_snapshot(self) -> Dict[str, Any]:
        runtimes = self.capability_engine.detect_runtimes()
        detected = AIWorkloadDetector.detect()
        return {"runtimes": runtimes, "workloads": detected["workloads"], "errors": detected["errors"]}