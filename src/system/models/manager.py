from __future__ import annotations

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

    def recommend(self, metadata: ModelMetadata, hardware: Dict[str, Any], runtime: Optional[Dict[str, Any]] = None, profile: str = "balanced") -> Dict[str, Any]:
        return self.recommendation_engine.recommend(hardware, metadata, runtime, profile)