import json

from src.system.hardware.capabilities import AVAILABLE, INSTALLED_BUT_BROKEN, NOT_INSTALLED, CapabilityEngine
from src.system.hardware.providers import CPUProvider, GPUProvider, StorageProvider


def test_cpu_detection_exposes_core_and_instruction_fields():
    result = CPUProvider.detect()
    assert result["logical_cores"] >= 1
    assert result["physical_cores"] is None or result["physical_cores"] >= 1
    assert isinstance(result["supported_instruction_sets"], list)
    assert result["architecture"]
    json.dumps(result)


def test_storage_detection_includes_mounts_and_model_locations():
    result = StorageProvider.detect()
    assert isinstance(result["disks"], list)
    paths = {item["path"] for item in result["model_locations"]}
    assert "/data/models" in paths
    assert any(item["mount_point"] == "/" for item in result["disks"])


def test_gpu_detection_has_explicit_no_gpu_or_vendor_status():
    result = GPUProvider.detect()
    assert result["vendor"] in {"none", "nvidia", "amd", "intel", "unknown"}
    assert result["status"] in {"available", "installed_but_broken", "unsupported"}


def test_capability_engine_has_structured_runtime_states(monkeypatch):
    monkeypatch.setattr("src.system.hardware.capabilities.shutil.which", lambda name: "/usr/bin/" + name if name == "python3" else None)
    monkeypatch.setattr("src.system.hardware.capabilities.importlib.util.find_spec", lambda name: None)
    result = CapabilityEngine().detect_runtimes()
    assert result["python"] == AVAILABLE
    assert result["pytorch"] == NOT_INSTALLED
    assert result["ollama"] == NOT_INSTALLED


def test_capability_engine_reports_broken_module_probe(monkeypatch):
    class BrokenSpec:
        pass

    monkeypatch.setattr("src.system.hardware.capabilities.importlib.util.find_spec", lambda name: BrokenSpec())
    monkeypatch.setattr("src.system.hardware.capabilities.subprocess.run", lambda *args, **kwargs: type("Result", (), {"returncode": 1})())
    assert CapabilityEngine().detect_runtimes()["pytorch"] == INSTALLED_BUT_BROKEN
