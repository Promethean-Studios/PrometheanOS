from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .metadata import ModelMetadata
from .providers import FilesystemModelProvider, HuggingFaceProvider, ModelProvider, OllamaProvider
from .recommendations import RecommendationEngine


class ModelManager:
    """Aggregate provider-neutral model discovery and recommendations."""

    def __init__(self, locations: Optional[Iterable[Path | str]] = None, providers: Optional[Iterable[ModelProvider]] = None):
        self.locations = [Path(path).expanduser() for path in (locations or ("/data/models", "~/.cache/huggingface", "~/.ollama", "/var/lib/ollama"))]
        self.providers = list(providers or (HuggingFaceProvider(), OllamaProvider(), FilesystemModelProvider()))
        self.recommendation_engine = RecommendationEngine()

    def discover(self) -> List[ModelMetadata]:
        models: List[ModelMetadata] = []
        for provider in self.providers:
            models.extend(provider.discover(self.locations))
        return models

    def launch(self, model_name: str) -> Dict[str, Any]:
        """Start an installed Ollama model, or return an actionable error."""
        if not model_name.strip():
            return {"ok": False, "error": "A model name is required."}
        if not any(model.name == model_name for model in self.discover()):
            return {"ok": False, "error": f"Model '{model_name}' is not installed."}
        ollama = shutil.which("ollama")
        if not ollama:
            return {"ok": False, "error": "Ollama is not installed; install it before launching a model."}
        try:
            process = subprocess.Popen(
                [ollama, "run", model_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            return {"ok": False, "error": f"Could not launch Ollama: {exc}"}
        return {"ok": True, "model": model_name, "pid": process.pid}

    def recommend(self, metadata: ModelMetadata, hardware: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None, profile: str = "balanced") -> Dict[str, Any]:
        return self.recommendation_engine.recommend(hardware, metadata, runtime, profile)