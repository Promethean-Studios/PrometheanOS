from types import SimpleNamespace

from src.system.telemetry import AIWorkloadDetector, SystemTelemetryCollector


def _empty_providers(monkeypatch):
    for provider in ("GPUProvider", "MemoryProvider", "StorageProvider", "NetworkProvider"):
        monkeypatch.setattr(f"src.system.telemetry.{provider}.detect", lambda: {})
    monkeypatch.setattr("src.system.telemetry.CapabilityEngine.detect", lambda self: {})


def test_collector_caches_snapshot_until_interval(monkeypatch):
    calls = {"cpu": 0}

    def cpu():
        calls["cpu"] += 1
        return {"load_percent": 12.5}

    monkeypatch.setattr("src.system.telemetry.CPUProvider.detect", cpu)
    _empty_providers(monkeypatch)
    collector = SystemTelemetryCollector(poll_interval=60)

    first = collector.snapshot()
    second = collector.snapshot()

    assert first is second
    assert calls["cpu"] == 1
    assert first["timestamp"].endswith("Z")


def test_collector_degrades_when_sensor_provider_fails(monkeypatch):
    monkeypatch.setattr("src.system.telemetry.CPUProvider.detect", lambda: (_ for _ in ()).throw(OSError("no sensor")))
    _empty_providers(monkeypatch)

    snapshot = SystemTelemetryCollector(poll_interval=0).snapshot()

    assert snapshot["cpu"] == {}
    assert snapshot["errors"]["cpu"] == "cpu: OSError"
    assert snapshot["gpu"] == {}


def test_ai_detector_ignores_unrelated_python_and_reports_model_process():
    processes = [
        SimpleNamespace(info={"pid": 1, "name": "python", "cmdline": ["python", "backup.py"], "memory_info": {"rss": 1}}),
        SimpleNamespace(info={"pid": 2, "name": "python", "cmdline": ["python", "-m", "vllm.entrypoints", "--model", "org/model"], "memory_info": {"rss": 1024 * 1024}}),
    ]

    result = AIWorkloadDetector.detect(lambda *_: processes)

    assert len(result["workloads"]) == 1
    assert result["workloads"][0]["workload"] == "vllm"
    assert result["workloads"][0]["model"] == "org/model"
