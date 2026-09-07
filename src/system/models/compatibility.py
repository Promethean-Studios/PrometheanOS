from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.system.telemetry import SystemTelemetryCollector


CATEGORIES = ("Excellent", "Good", "Heavy", "Not Recommended", "Unsupported")


@dataclass(frozen=True)
class ModelSizeBand:
    name: str
    minimum_billions: float
    maximum_billions: Optional[float]


MODEL_SIZE_BANDS = (
    ModelSizeBand("1B-3B", 1, 3),
    ModelSizeBand("7B-8B", 7, 8),
    ModelSizeBand("14B", 14, 14),
    ModelSizeBand("30B-32B", 30, 32),
    ModelSizeBand("70B+", 70, 99),
    ModelSizeBand("larger models", 100, None),
)


def _number(value: Any) -> Optional[float]:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _quantization_bits(value: Any) -> float:
    quantization = str(value or "").lower()
    if any(token in quantization for token in ("q2", "2-bit", "2bit")):
        return 2.75
    if any(token in quantization for token in ("q3", "3-bit", "3bit")):
        return 3.75
    if any(token in quantization for token in ("q4", "4-bit", "4bit")):
        return 4.5
    if any(token in quantization for token in ("q5", "5-bit", "5bit")):
        return 5.5
    if any(token in quantization for token in ("q8", "8-bit", "8bit", "int8")):
        return 8.5
    return 16.0


def _size_band(parameter_count: Any) -> Optional[ModelSizeBand]:
    parameters = _number(parameter_count)
    if parameters is None or parameters <= 0:
        return None
    billions = parameters / 1_000_000_000
    for band in MODEL_SIZE_BANDS:
        if billions >= band.minimum_billions and (band.maximum_billions is None or billions <= band.maximum_billions):
            return band
    return MODEL_SIZE_BANDS[-1] if billions > MODEL_SIZE_BANDS[-1].minimum_billions else None


def _gpu_devices(hardware: Dict[str, Any]) -> list[Dict[str, Any]]:
    gpu = hardware.get("gpu") or {}
    devices = gpu.get("gpus")
    if isinstance(devices, list) and devices:
        return [item for item in devices if isinstance(item, dict)]
    return [gpu] if isinstance(gpu, dict) and gpu.get("vendor") not in {None, "none", "unknown"} else []


class HardwareCompatibilityEngine:
    """Estimate local model fit from the existing system telemetry snapshot.

    Results are heuristics, not guarantees. Runtime, context length, kernels,
    and model architecture can materially change actual requirements.
    """

    def __init__(self, telemetry: Optional[SystemTelemetryCollector] = None):
        self.telemetry = telemetry or SystemTelemetryCollector()

    def current_hardware(self) -> Dict[str, Any]:
        return self.telemetry.snapshot()

    def assess(self, metadata: Dict[str, Any], hardware: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        hardware = hardware or self.current_hardware()
        parameters = _number(metadata.get("parameter_count"))
        band = _size_band(parameters)
        quantization = metadata.get("quantization")
        bits = _quantization_bits(quantization)
        artifact_bytes = _number(metadata.get("file_size_bytes")) or _number(metadata.get("download_size_bytes"))
        weight_mb = artifact_bytes / 1024**2 if artifact_bytes is not None and artifact_bytes >= 0 else (
            parameters * bits / 8 / 1024**2 if parameters is not None else None
        )
        context = _number(metadata.get("context_length")) or 4096
        context_factor = min(max(context / 4096, 1), 16)
        runtime_overhead = 1.15 + min(context_factor * 0.03, 0.48)
        required_mb = weight_mb * runtime_overhead if weight_mb is not None else None
        available_ram = _number((hardware.get("memory") or {}).get("available_mb"))
        storage_free_gb = _number((hardware.get("storage") or {}).get("free_gb"))
        gpus = _gpu_devices(hardware)
        gpu_vram = max((_number(gpu.get("vram_mb")) or 0 for gpu in gpus), default=0) or None
        gpu_fit = required_mb is not None and gpu_vram is not None and gpu_vram >= required_mb
        cpu_fit = required_mb is not None and available_ram is not None and available_ram >= required_mb * 1.1
        storage_fit = weight_mb is not None and storage_free_gb is not None and storage_free_gb * 1024 >= weight_mb * 1.1
        compute = [gpu.get("compute_capability") or gpu.get("compute") for gpu in gpus]
        compute = [value for value in compute if value is not None]
        cpu = hardware.get("cpu") or {}

        if required_mb is None or available_ram is None or storage_free_gb is None:
            category = "Unsupported"
            reason = "model size, available RAM, or available storage is unknown"
        elif not storage_fit or not cpu_fit:
            category = "Not Recommended"
            reason = "the estimated model footprint exceeds available storage or system RAM"
        elif gpu_fit and gpu_vram >= required_mb * 1.5:
            category = "Excellent"
            reason = "estimated working memory fits in GPU VRAM with headroom"
        elif gpu_fit or (cpu_fit and required_mb <= available_ram * 0.65):
            category = "Good"
            reason = "estimated working memory fits a reported memory pool"
        else:
            category = "Heavy"
            reason = "the model may fit, but leaves limited memory headroom or requires CPU inference"

        return {
            "estimate": True,
            "category": category,
            "model_size_band": band.name if band else "unknown",
            "model_parameter_count": parameters,
            "quantization": quantization or "unknown",
            "estimated_weight_mb": round(weight_mb, 2) if weight_mb is not None else None,
            "estimated_required_mb": round(required_mb, 2) if required_mb is not None else None,
            "available_ram_mb": available_ram,
            "available_vram_mb": gpu_vram,
            "available_storage_gb": storage_free_gb,
            "hardware": {
                "cpu_model": cpu.get("model") or cpu.get("architecture"),
                "physical_cores": cpu.get("physical_cores"),
                "logical_threads": cpu.get("logical_cores") or cpu.get("cores"),
                "total_ram_mb": _number((hardware.get("memory") or {}).get("total_mb")),
                "available_ram_mb": available_ram,
                "gpu_models": [gpu.get("model") or gpu.get("name") for gpu in gpus],
                "gpu_compute_capabilities": compute,
                "available_storage_gb": storage_free_gb,
            },
            "cpu_inference": {"supported": cpu_fit, "estimated": True},
            "gpu_inference": {"supported": gpu_fit, "estimated": True, "compute_capabilities": compute},
            "reason": reason,
            "evidence": "estimate based on model parameters, quantization, available memory, storage, and runtime overhead; actual fit varies",
        }


def estimate_compatibility(metadata: Dict[str, Any], hardware: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible entry point for compatibility estimates."""
    return HardwareCompatibilityEngine().assess(metadata, hardware)