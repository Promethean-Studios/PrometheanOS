from __future__ import annotations

import json
from typing import Any, Dict, List

from src.system.hardware.capabilities import CapabilityEngine
from src.system.telemetry import AIWorkloadDetector, SystemTelemetryCollector


class PrometheanService:
    """Read-only system service for local AI and hardware monitoring."""

    def __init__(self, telemetry: SystemTelemetryCollector = None, poll_interval: float = 2.0):
        self.name = "promethean-system"
        self.version = "0.1.0"
        self.capability_engine = CapabilityEngine()
        self.telemetry = telemetry or SystemTelemetryCollector(poll_interval=poll_interval, capability_engine=self.capability_engine)

    def snapshot(self) -> Dict[str, Any]:
        snapshot = self.telemetry.snapshot()
        return {
            "service": {"name": self.name, "version": self.version},
            **snapshot,
        }

    def get_ai_status(self, runtimes: Dict[str, str] = None) -> Dict[str, Any]:
        runtimes = runtimes or self.capability_engine.detect_runtimes()

        return {
            "runtimes": runtimes,
            "ai_workloads": self.get_ai_workloads(),
        }

    def get_ai_workloads(self) -> List[Dict[str, Any]]:
        return AIWorkloadDetector.detect()["workloads"]

    def get_permissions(self) -> Dict[str, str]:
        return {
            "read_system_information": "allowed",
            "install_software": "requires_explicit_confirmation",
            "modify_configuration": "requires_explicit_confirmation",
            "execute_commands": "requires_explicit_confirmation",
            "delete_files": "requires_explicit_confirmation",
            "root_administrator_actions": "requires_explicit_confirmation",
        }

    def status(self) -> Dict[str, Any]:
        return {"status": "ok", "snapshot": self.snapshot()}

    def to_json(self) -> str:
        return json.dumps(self.snapshot(), indent=2, sort_keys=True)
