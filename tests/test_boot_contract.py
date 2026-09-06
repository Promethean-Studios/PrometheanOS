from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_build_contract_is_self_contained():
    build = (ROOT / "build.sh").read_text(encoding="utf-8")
    live = (ROOT / "kickstarts/promethean-live.ks").read_text(encoding="utf-8")

    assert "promethean-live.ks" in build
    assert "--make-iso" in build
    directives = {line.split(maxsplit=1)[0] for line in live.splitlines() if line and not line.startswith("#")}
    assert "clearpart" not in directives
    assert "autopart" not in directives
    assert "reboot" not in directives
    assert "/srv/promethean" in live
    assert "promethean-api.service" in live


def test_boot_services_have_installed_paths_and_optional_ollama():
    api = (ROOT / "systemd/promethean-api.service").read_text(encoding="utf-8")
    hardware = (ROOT / "systemd/promethean-hardware-detect.service").read_text(encoding="utf-8")
    ollama = (ROOT / "systemd/promethean-ollama.service").read_text(encoding="utf-8")

    assert "WorkingDirectory=/srv/promethean" in api
    assert "Environment=PYTHONPATH=/srv/promethean" in api
    assert "/usr/bin/env bash /usr/local/libexec/promethean/hardware-detect.sh" in hardware
    assert "ConditionPathExists=/usr/bin/ollama" in ollama
    assert "127.0.0.1:11434" in ollama


def test_boot_hardware_probe_is_read_only_and_cpu_safe():
    script = (ROOT / "promethean-hardware-detect.sh").read_text(encoding="utf-8")

    assert "dnf install" not in script
    assert "akmod" not in script
    assert "chmod 0666" not in script
    assert "CPU-only or GPU telemetry unavailable" in script
