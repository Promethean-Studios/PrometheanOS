import types
from unittest.mock import Mock, patch

import pytest

from src.system.hardware_monitor import HardwareMonitor


@patch("src.system.hardware_monitor.psutil.process_iter")
def test_detect_ai_workloads_filters_known_ai_processes(mock_process_iter):
    process_a = Mock()
    process_a.info = {
        "pid": 101,
        "name": "ollama",
        "cmdline": ["/usr/bin/ollama", "serve"],
        "memory_info": {"rss": 512 * 1024 * 1024},
    }
    process_b = Mock()
    process_b.info = {
        "pid": 202,
        "name": "bash",
        "cmdline": ["bash", "-lc", "echo hi"],
        "memory_info": {"rss": 10 * 1024 * 1024},
    }
    mock_process_iter.return_value = [process_a, process_b]

    workloads = HardwareMonitor.detect_ai_workloads()

    assert len(workloads) == 1
    assert workloads[0]["pid"] == 101
    assert workloads[0]["name"] == "ollama"


@patch("src.system.hardware_monitor.psutil.sensors_temperatures")
def test_get_cpu_temp_c_reads_psutil_sensor(mock_sensors):
    mock_sensors.return_value = {
        "coretemp": [types.SimpleNamespace(current=61.5)],
        "k10temp": [types.SimpleNamespace(current=58.2)],
    }

    assert HardwareMonitor.get_cpu_temp_c() == pytest.approx(59.85)


@patch("src.system.hardware_monitor.shutil.which")
@patch("src.system.hardware_monitor.subprocess.run")
def test_get_vram_usage_mb_reads_nvidia_smi(mock_run, mock_which):
    mock_which.return_value = "/usr/bin/nvidia-smi"
    mock_run.return_value.stdout = "1200, 4000\n"

    usage = HardwareMonitor.get_vram_usage_mb()

    assert usage["used_mb"] == 1200
    assert usage["total_mb"] == 4000
