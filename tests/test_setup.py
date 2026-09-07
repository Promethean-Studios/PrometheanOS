from src.system.setup import SETUP_STEPS, SetupState


class FakeTelemetry:
    def snapshot(self, force=False):
        return {
            "cpu": {"model": "Setup CPU", "physical_cores": 4, "logical_cores": 8},
            "memory": {"total_mb": 16384, "available_mb": 12000},
            "gpu": {"vendor": "none", "status": "unsupported", "gpus": []},
            "storage": {"free_gb": 100},
            "network": {"interfaces": {"eth0": {"active": True, "addresses": ["192.0.2.2"]}}},
            "ai": {"runtimes": {}},
        }


def test_setup_state_persists_choices_and_completion(tmp_path):
    setup = SetupState(tmp_path / "setup.json", telemetry=FakeTelemetry())

    initial = setup.snapshot()
    assert initial["state"]["completed"] is False
    assert initial["steps"] == SETUP_STEPS
    assert initial["offline_completion"] is True
    assert initial["recommendations"]

    setup.update({"step": "hardware", "language": "en_GB", "user": {"display_name": "Operator"}})
    completed = setup.complete({"ai": {"skipped": True}})

    assert completed["completed"] is True
    assert completed["language"] == "en_GB"
    assert completed["ai"]["skipped"] is True
    assert SetupState(tmp_path / "setup.json", telemetry=FakeTelemetry()).read()["completed"] is True


def test_setup_falls_back_to_user_config_when_system_path_is_unwritable(tmp_path, monkeypatch):
    requested = tmp_path / "system" / "setup.json"
    original_mkdir = requested.parent.__class__.mkdir
    calls = {"count": 0}

    def fail_once(path, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("read only")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(requested.parent.__class__, "mkdir", fail_once)

    setup = SetupState(requested, telemetry=FakeTelemetry())

    assert setup.path.name == "setup.json"
    assert setup.path != requested
