from src.system.models.compatibility import CATEGORIES, HardwareCompatibilityEngine


def hardware(ram_mb=65536, storage_gb=500, vram_mb=24576, gpu="nvidia"):
    return {
        "cpu": {"model": "Test CPU", "physical_cores": 8, "logical_cores": 16},
        "memory": {"total_mb": ram_mb + 8192, "available_mb": ram_mb},
        "gpu": {
            "vendor": gpu,
            "name": "Test GPU",
            "vram_mb": vram_mb,
            "compute_capability": "8.6" if gpu != "none" else None,
        },
        "storage": {"free_gb": storage_gb},
    }


def test_supported_size_bands_are_explicit_and_estimated():
    engine = HardwareCompatibilityEngine()
    sizes = (1, 7, 14, 30, 70, 100)

    results = [engine.assess({"parameter_count": size * 1_000_000_000, "quantization": "Q4_K_M"}, hardware()) for size in sizes]

    assert [result["model_size_band"] for result in results] == ["1B-3B", "7B-8B", "14B", "30B-32B", "70B+", "larger models"]
    assert all(result["estimate"] is True for result in results)
    assert all(result["category"] in CATEGORIES for result in results)


def test_gpu_headroom_is_excellent_and_reports_compute_capability():
    result = HardwareCompatibilityEngine().assess(
        {"parameter_count": 7_000_000_000, "quantization": "Q4_K_M"},
        hardware(),
    )

    assert result["category"] == "Excellent"
    assert result["gpu_inference"]["supported"] is True
    assert result["gpu_inference"]["compute_capabilities"] == ["8.6"]
    assert "actual fit varies" in result["evidence"]


def test_cpu_only_and_limited_hardware_are_distinguished():
    engine = HardwareCompatibilityEngine()
    cpu_only = engine.assess(
        {"parameter_count": 30_000_000_000, "quantization": "Q4"},
        hardware(ram_mb=24_000, vram_mb=None, gpu="none"),
    )
    limited = engine.assess(
        {"parameter_count": 14_000_000_000, "quantization": "Q4"},
        hardware(ram_mb=8_000, storage_gb=2, vram_mb=None, gpu="none"),
    )

    assert cpu_only["category"] == "Heavy"
    assert cpu_only["cpu_inference"]["supported"] is True
    assert cpu_only["gpu_inference"]["supported"] is False
    assert limited["category"] == "Not Recommended"


def test_missing_measurements_are_unsupported_not_invented():
    result = HardwareCompatibilityEngine().assess(
        {"parameter_count": 7_000_000_000, "quantization": "Q4"},
        {"memory": {"available_mb": None}, "gpu": {"vendor": "none"}, "storage": {"free_gb": None}},
    )

    assert result["category"] == "Unsupported"
    assert result["estimated_required_mb"] is not None
    assert result["available_vram_mb"] is None