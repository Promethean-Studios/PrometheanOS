from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .metadata import ModelMetadata


PROFILES = {"balanced", "ai_performance", "low_end", "developer"}


@dataclass(frozen=True)
class Recommendation:
    value: Any
    basis: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {"value": self.value, "basis": self.basis, "rationale": self.rationale}


def _recommend(value: Any, basis: str, rationale: str) -> Dict[str, Any]:
    return Recommendation(value, basis, rationale).to_dict()


def _number(value: Any) -> Optional[float]:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _memory_estimate_mb(metadata: ModelMetadata, context_length: Optional[int]) -> Optional[float]:
    """Estimate working memory from known artifact size or parameter count.

    Runtime allocations vary substantially, so this is intentionally an estimate.
    """
    size = _number(metadata.file_size_bytes) or _number(metadata.download_size_bytes)
    if size is not None and size >= 0:
        weights_mb = size / (1024 * 1024)
    elif _number(metadata.parameter_count) is not None:
        bits = 16.0
        quantization = (metadata.quantization or "").lower()
        if "4" in quantization or "q4" in quantization:
            bits = 4.5
        elif "8" in quantization or "q8" in quantization:
            bits = 8.5
        weights_mb = metadata.parameter_count * bits / 8 / (1024 * 1024)
    else:
        return None
    context_factor = min(max((context_length or 4096) / 4096, 1.0), 16.0)
    return round(weights_mb * (1.15 + min(context_factor * 0.03, 0.48)), 2)


class RecommendationEngine:
    """Produce read-only, evidence-labelled model configuration guidance."""

    def recommend(
        self,
        hardware: Dict[str, Any],
        metadata: ModelMetadata,
        runtime: Optional[Dict[str, Any]] = None,
        profile: str = "balanced",
    ) -> Dict[str, Any]:
        profile = profile.lower().replace("-", "_").replace(" ", "_")
        if profile not in PROFILES:
            raise ValueError(f"unknown profile: {profile}")
        runtime = runtime or {}
        context = metadata.context_length if isinstance(metadata.context_length, int) and metadata.context_length > 0 else None
        required_mb = _memory_estimate_mb(metadata, context)
        available_ram = _number(hardware.get("memory", {}).get("available_mb"))
        available_vram = _number(hardware.get("gpu", {}).get("vram_mb"))
        gpu_present = hardware.get("gpu", {}).get("vendor") not in {None, "none", "unknown"}
        runtime_names = runtime.get("available") or runtime.get("runtimes") or runtime
        if isinstance(runtime_names, dict):
            gpu_runtime = any(str(runtime_names.get(name, "")).lower() in {"available", "true"} for name in ("cuda", "rocm", "ollama", "vllm", "llama_cpp"))
        else:
            gpu_runtime = False

        ram_fit = required_mb is not None and available_ram is not None and available_ram >= required_mb
        vram_fit = required_mb is not None and available_vram is not None and available_vram >= required_mb
        if required_mb is None:
            status = "unknown"
            status_reason = "model size and parameter count are unavailable"
        elif ram_fit or vram_fit:
            status = "likely_usable"
            status_reason = "estimated working memory fits an available memory pool"
        else:
            status = "unlikely_usable"
            status_reason = "estimated working memory exceeds the reported available memory"

        context_value = context or 4096
        if profile == "low_end":
            context_value = min(context_value, 2048)
        elif profile == "developer":
            context_value = min(context_value, 8192)
        elif profile == "balanced":
            context_value = min(context_value, 4096)
        batch = 1 if required_mb is None else (4 if profile == "ai_performance" and (vram_fit or ram_fit) else 1)
        threads = _number(hardware.get("cpu", {}).get("logical_cores")) or _number(hardware.get("cpu", {}).get("cores"))
        if threads is not None:
            threads = max(1, min(int(threads), 16 if profile != "ai_performance" else 32))

        quantization = metadata.quantization
        if required_mb is not None and available_vram is not None and required_mb > available_vram:
            quantization_value = "consider a lower-bit quantization"
            quantization_basis = "heuristic"
            quantization_reason = "the current memory estimate exceeds available VRAM"
        elif quantization:
            quantization_value = quantization
            quantization_basis = "known"
            quantization_reason = "using the quantization reported by model metadata"
        else:
            quantization_value = "retain source precision unless memory pressure is observed"
            quantization_basis = "heuristic"
            quantization_reason = "quantization was not provided by the model source"

        offload = "GPU-first" if gpu_present and gpu_runtime and profile in {"balanced", "ai_performance"} else "CPU-first"
        if profile == "low_end":
            offload = "CPU-first with optional partial GPU offload"
        return {
            "model": metadata.to_dict(),
            "profile": profile,
            "status": _recommend(status, "estimate" if required_mb is not None else "unknown", status_reason),
            "ram_requirement_mb": _recommend(required_mb, "estimate", "weights plus a conservative runtime/context allowance") if required_mb is not None else _recommend(None, "unknown", "model size and parameter count are unavailable"),
            "vram_requirement_mb": _recommend(required_mb, "estimate", "VRAM depends on runtime placement, context, and offload strategy") if required_mb is not None else _recommend(None, "unknown", "model size and parameter count are unavailable"),
            "quantization": _recommend(quantization_value, quantization_basis, quantization_reason),
            "offload": _recommend(offload, "heuristic", "chosen from reported GPU/runtime availability and the selected profile"),
            "context_length": _recommend(context_value, "known" if context else "heuristic", "capped for the selected profile to control memory use"),
            "batch_size": _recommend(batch, "heuristic", "smaller batches reduce memory pressure; larger batches favor throughput"),
            "threads": _recommend(threads, "measured" if threads is not None else "unknown", "bounded from reported logical CPU capacity"),
            "expected_bottlenecks": [
                _recommend("memory capacity", "estimate", "working memory is the primary limiting factor for local inference"),
                _recommend("context or batch size", "heuristic", "increasing either usually increases temporary memory use"),
            ],
            "evidence": {
                "hardware": "measured where provided by the hardware capability engine",
                "model_metadata": "known only where supplied by a provider",
                "runtime": "known only where detected or supplied",
                "recommendations": "estimates and heuristics; not guaranteed inference requirements",
            },
        }