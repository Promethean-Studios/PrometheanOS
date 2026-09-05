import json
from threading import Thread

import pytest

from src.system.api.local_api import LocalPrometheanAPI
from src.system.hardware.providers import GPUProvider, HardwareProvider
from src.system.services.promethean_service import PrometheanService


class FakeGPUProvider(GPUProvider):
    @staticmethod
    def detect_gpu():
        return {"vendor": "unknown", "name": "no-supported-gpu", "family": "cpu-only"}


class FakeCPUProvider:
    def __init__(self):
        self.cpu = {"model": "Fake CPU", "cores": 4, "load_percent": 25.0}


def test_gpu_provider_reports_unsupported_hardware():
    provider = FakeGPUProvider()
    result = provider.detect_gpu()
    assert result["vendor"] == "unknown"
    assert result["family"] == "cpu-only"


def test_promethean_service_snapshot_includes_expected_sections():
    service = PrometheanService()
    snapshot = service.snapshot()
    assert "cpu" in snapshot
    assert "gpu" in snapshot
    assert "storage" in snapshot
    assert "network" in snapshot
    assert "ai" in snapshot


def test_service_startup_and_health_endpoint():
    api = LocalPrometheanAPI(service=PrometheanService(), host="127.0.0.1", port=8766)
    thread = Thread(target=api.serve_forever, daemon=True)
    thread.start()
    assert api.wait_until_ready(timeout=5)
    import urllib.request

    resp = urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=5)
    payload = json.loads(resp.read().decode())
    assert payload["status"] == "ok"
    api.shutdown()
    thread.join(timeout=5)


def test_api_rejects_malformed_or_private_paths():
    api = LocalPrometheanAPI(service=PrometheanService(), host="127.0.0.1", port=8767)
    thread = Thread(target=api.serve_forever, daemon=True)
    thread.start()
    assert api.wait_until_ready(timeout=5)
    import urllib.request
    import urllib.error

    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen("http://127.0.0.1:8767/not-real", timeout=5)

    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen("http://127.0.0.1:8767/", timeout=5)

    api.shutdown()
    thread.join(timeout=5)


def test_api_serves_control_center_and_live_telemetry():
    api = LocalPrometheanAPI(service=PrometheanService(), host="127.0.0.1", port=8768)
    thread = Thread(target=api.serve_forever, daemon=True)
    thread.start()
    assert api.wait_until_ready(timeout=5)
    import urllib.request

    html = urllib.request.urlopen("http://127.0.0.1:8768/control-center", timeout=5).read().decode()
    telemetry = json.loads(urllib.request.urlopen("http://127.0.0.1:8768/telemetry", timeout=5).read())
    assert "Promethean Control Center" in html
    assert {"cpu", "memory", "gpu", "storage", "network", "ai"}.issubset(telemetry)
    api.shutdown()
    thread.join(timeout=5)


def test_unsafely_implemented_permission_boundaries():
    service = PrometheanService()
    permissions = service.get_permissions()
    assert "read_system_information" in permissions
    assert "root_administrator_actions" in permissions
    assert permissions["root_administrator_actions"] == "requires_explicit_confirmation"
