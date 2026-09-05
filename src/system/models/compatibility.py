from __future__ import annotations

from typing import Any, Dict


def estimate_compatibility(metadata: Dict[str, Any], hardware: Dict[str, Any]) -> Dict[str, Any]:
    """Return conservative estimates, never an exact inference requirement."""
    size = metadata.get("file_size_bytes") or metadata.get("download_size_bytes")
    if not isinstance(size, (int, float)):
        return {"estimate": True, "status": "unknown", "reason": "model size is unknown", "ram_mb": None, "vram_mb": None}
    quantization = str(metadata.get("quantization") or "").lower()
    overhead = 1.15 if quantization else 1.35
    context = metadata.get("context_length")
    if isinstance(context, int) and context > 0:
        overhead += min(context / 32768 * 0.25, 0.5)
    required_mb = size / 1024**2 * overhead
    ram_mb = hardware.get("memory", {}).get("available_mb")
    vram_mb = hardware.get("gpu", {}).get("vram_mb")
    return {"estimate": True, "status": "likely_fit" if isinstance(ram_mb, (int, float)) and ram_mb >= required_mb else "may_not_fit", "reason": "estimated model storage multiplied by runtime and context overhead", "estimated_required_mb": round(required_mb, 2), "ram_mb": ram_mb, "vram_mb": vram_mb, "ram_likely_fit": ram_mb >= required_mb if isinstance(ram_mb, (int, float)) else None, "vram_likely_fit": vram_mb >= required_mb if isinstance(vram_mb, (int, float)) else None}