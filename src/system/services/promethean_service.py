from __future__ import annotations

import json
from typing import Any, Dict, List

from src.system.hardware.capabilities import CapabilityEngine
from src.system.models import ModelManager, ModelMetadata
from src.system.security import PermissionBroker
from src.system.setup import SetupState
from src.system.telemetry import AIWorkloadDetector, SystemTelemetryCollector


class PrometheanService:
    """Read-only system service for local AI and hardware monitoring."""

    def __init__(self, telemetry: SystemTelemetryCollector = None, poll_interval: float = 2.0, model_manager: ModelManager = None, permission_broker: PermissionBroker = None):
        self.name = "promethean-system"
        self.version = "0.1.0"
        self.capability_engine = CapabilityEngine()
        self.telemetry = telemetry or SystemTelemetryCollector(poll_interval=poll_interval, capability_engine=self.capability_engine)
        self.model_manager = model_manager or ModelManager()
        self.setup = SetupState(telemetry=self.telemetry)
        self.permission_broker = permission_broker or PermissionBroker()

    def get_models(self) -> List[Dict[str, Any]]:
        return self.model_manager.installed()

    def search_models(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.model_manager.search(query, limit)

    def get_setup(self) -> Dict[str, Any]:
        return self.setup.snapshot()

    def update_setup(self, values: Dict[str, Any], complete: bool = False) -> Dict[str, Any]:
        return self.setup.complete(values) if complete else self.setup.update(values)

    def recommend_model(self, model: ModelMetadata, profile: str = "balanced") -> Dict[str, Any]:
        snapshot = self.snapshot()
        return self.model_manager.recommend(model, snapshot, snapshot.get("ai", {}).get("runtimes", {}), profile)

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
        legacy = {
            "read_system_information": "allowed",
            "install_software": "requires_explicit_confirmation",
            "modify_configuration": "requires_explicit_confirmation",
            "execute_commands": "requires_explicit_confirmation",
            "delete_files": "requires_explicit_confirmation",
            "root_administrator_actions": "requires_explicit_confirmation",
        }
        return {"operations": self.permission_broker.describe(), **legacy}

    def request_permission(self, request):
        return self.permission_broker.request(request).to_dict()

    def status(self) -> Dict[str, Any]:
        return {"status": "ok", "snapshot": self.snapshot()}

    def to_json(self) -> str:
        return json.dumps(self.snapshot(), indent=2, sort_keys=True)
