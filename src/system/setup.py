from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.system.models.compatibility import HardwareCompatibilityEngine
from src.system.telemetry import SystemTelemetryCollector


SETUP_STEPS = ("welcome", "language", "network", "user", "hardware", "ai", "models", "finish")

# Metadata is intentionally limited to known public models. It is used only for
# offline recommendations; no model is downloaded or installed by setup.
RECOMMENDED_MODELS = (
    {"name": "Qwen2.5 1.5B Instruct", "repository_id": "Qwen/Qwen2.5-1.5B-Instruct", "parameter_count": 1_500_000_000, "quantization": "Q4", "context_length": 32768, "model_format": "safetensors"},
    {"name": "Qwen2.5 3B Instruct", "repository_id": "Qwen/Qwen2.5-3B-Instruct", "parameter_count": 3_000_000_000, "quantization": "Q4", "context_length": 32768, "model_format": "safetensors"},
    {"name": "Llama 3.2 3B Instruct", "repository_id": "meta-llama/Llama-3.2-3B-Instruct", "parameter_count": 3_000_000_000, "quantization": "Q4", "context_length": 131072, "model_format": "safetensors"},
    {"name": "Qwen2.5 7B Instruct", "repository_id": "Qwen/Qwen2.5-7B-Instruct", "parameter_count": 7_000_000_000, "quantization": "Q4", "context_length": 32768, "model_format": "safetensors"},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SetupState:
    """Persist first-run choices without changing privileged system state."""

    def __init__(self, path: Optional[Path | str] = None, telemetry: Optional[SystemTelemetryCollector] = None):
        requested = Path(path or os.environ.get("PROMETHEAN_SETUP_STATE", "/var/lib/promethean/setup.json")).expanduser().resolve()
        try:
            requested.parent.mkdir(parents=True, exist_ok=True)
            self.path = requested
        except OSError:
            self.path = (Path.home() / ".config" / "promethean" / "setup.json").resolve()
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.telemetry = telemetry or SystemTelemetryCollector()
        self.compatibility = HardwareCompatibilityEngine(self.telemetry)

    def read(self) -> Dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else self._default()
        except (OSError, ValueError):
            return self._default()

    def update(self, values: Dict[str, Any]) -> Dict[str, Any]:
        state = self.read()
        for key in ("step", "language", "keyboard", "network", "user", "ai", "models"):
            if key in values and isinstance(values[key], (str, bool, dict, list, type(None))):
                state[key] = values[key]
        if values.get("completed") is True:
            state["completed"] = True
            state["completed_at"] = _now()
        self._write(state)
        return state

    def complete(self, values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.update({**(values or {}), "completed": True, "step": "finish"})

    def snapshot(self) -> Dict[str, Any]:
        hardware = self.telemetry.snapshot(force=True)
        recommendations = []
        for model in RECOMMENDED_MODELS:
            item = dict(model)
            item["compatibility"] = self.compatibility.assess(item, hardware)
            recommendations.append(item)
        return {"state": self.read(), "steps": SETUP_STEPS, "hardware": hardware, "recommendations": recommendations, "offline_completion": True}

    def _default(self) -> Dict[str, Any]:
        return {"completed": False, "step": "welcome", "language": "en_US", "keyboard": "us", "network": {}, "user": {}, "ai": {"skipped": False}, "models": {}}

    def _write(self, state: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="setup-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
