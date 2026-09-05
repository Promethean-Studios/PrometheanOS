from __future__ import annotations

import importlib.util
import shutil
import subprocess
from typing import Any, Dict, Optional

from .providers import GPUProvider, StorageProvider

AVAILABLE = "AVAILABLE"
INSTALLED_BUT_BROKEN = "INSTALLED_BUT_BROKEN"
NOT_INSTALLED = "NOT_INSTALLED"
UNSUPPORTED = "UNSUPPORTED"


def _module_status(module: str, probe: Optional[str] = None) -> str:
    if importlib.util.find_spec(module) is None:
        return NOT_INSTALLED
    if not probe:
        return AVAILABLE
    try:
        result = subprocess.run(["python3", "-c", probe], capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return INSTALLED_BUT_BROKEN
    return AVAILABLE if result.returncode == 0 else INSTALLED_BUT_BROKEN


def _binary_status(binary: str, args: Optional[list[str]] = None) -> str:
    path = shutil.which(binary)
    if not path:
        return NOT_INSTALLED
    try:
        result = subprocess.run([path, *(args or ["--version"])], capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return INSTALLED_BUT_BROKEN
    return AVAILABLE if result.returncode == 0 else INSTALLED_BUT_BROKEN


class CapabilityEngine:
    """Build a read-only, machine-readable summary of AI capabilities."""

    def detect_runtimes(self) -> Dict[str, str]:
        return {
            "python": _binary_status("python3", ["--version"]),
            "pytorch": _module_status("torch", "import torch; print(torch.__version__)"),
            "cuda": _module_status("torch", "import torch; assert torch.cuda.is_available()"),
            "rocm": _binary_status("rocminfo"),
            "llama_cpp": _module_status("llama_cpp"),
            "ollama": _binary_status("ollama"),
            "vllm": _module_status("vllm"),
            "onnx_runtime": _module_status("onnxruntime", "import onnxruntime"),
            "tensorrt": _module_status("tensorrt", "import tensorrt"),
            "huggingface": _module_status("transformers", "import transformers") if importlib.util.find_spec("transformers") else _binary_status("huggingface-cli"),
            "jupyter": _binary_status("jupyter", ["--version"]),
            "podman": _binary_status("podman", ["--version"]),
        }

    def detect(self) -> Dict[str, Any]:
        gpu = GPUProvider.detect()
        runtimes = self.detect_runtimes()
        storage = StorageProvider.detect()
        model_storage = any(item["exists"] and item["readable"] for item in storage["model_locations"])
        return {
            "capabilities": {
                "cpu_inference": AVAILABLE,
                "gpu_inference": AVAILABLE if gpu["status"] == "available" else UNSUPPORTED,
                "cuda_acceleration": runtimes["cuda"] if gpu["vendor"] == "nvidia" else UNSUPPORTED,
                "rocm_acceleration": runtimes["rocm"] if gpu["vendor"] == "amd" else UNSUPPORTED,
                "large_model_inference": AVAILABLE if storage["total_gb"] >= 100 and (gpu.get("vram_mb") or 0) >= 8192 else UNSUPPORTED,
                "quantized_inference": AVAILABLE if runtimes["llama_cpp"] == AVAILABLE or runtimes["ollama"] == AVAILABLE else UNSUPPORTED,
                "containerized_ai": runtimes["podman"],
                "local_model_storage": AVAILABLE if model_storage else NOT_INSTALLED,
            },
            "runtimes": runtimes,
            "gpu": gpu,
            "model_storage": storage["model_locations"],
        }
