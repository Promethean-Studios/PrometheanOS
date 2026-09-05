from src.system.models.metadata import ModelMetadata
from src.system.models.recommendations import RecommendationEngine


def hardware(ram=16384, vram=8192, cores=8, gpu="nvidia"):
    return {
        "memory": {"available_mb": ram},
        "gpu": {"vendor": gpu, "vram_mb": vram},
        "cpu": {"logical_cores": cores},
    }


def test_gpu_model_recommendation_labels_estimates_and_uses_gpu_runtime():
    model = ModelMetadata(name="small", file_size_bytes=4 * 1024**3, quantization="Q4_K_M", context_length=8192)
    result = RecommendationEngine().recommend(hardware(), model, {"cuda": "AVAILABLE"}, "AI Performance")

    assert result["status"]["value"] == "likely_usable"
    assert result["status"]["basis"] == "estimate"
    assert result["ram_requirement_mb"]["basis"] == "estimate"
    assert result["offload"]["value"] == "GPU-first"
    assert result["profile"] == "ai_performance"
    assert result["evidence"]["recommendations"].startswith("estimates")


def test_low_end_cpu_only_model_is_conservative():
    model = ModelMetadata(name="medium", file_size_bytes=10 * 1024**3, context_length=32768)
    result = RecommendationEngine().recommend(hardware(ram=4096, vram=None, cores=2, gpu="none"), model, {}, "low-end")

    assert result["status"]["value"] == "unlikely_usable"
    assert result["context_length"]["value"] == 2048
    assert result["batch_size"]["value"] == 1
    assert result["offload"]["value"] == "CPU-first with optional partial GPU offload"


def test_unknown_model_size_does_not_invent_memory_requirements():
    result = RecommendationEngine().recommend(hardware(), ModelMetadata(name="unknown"), {}, "developer")

    assert result["status"]["value"] == "unknown"
    assert result["ram_requirement_mb"]["value"] is None
    assert result["vram_requirement_mb"]["basis"] == "unknown"
    assert result["quantization"]["basis"] == "heuristic"