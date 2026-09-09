from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .compatibility import HardwareCompatibilityEngine
from .metadata import ModelMetadata
from .providers import (
    FilesystemModelProvider,
    HuggingFaceProvider,
    ModelProvider,
    OllamaProvider,
)
from .recommendations import RecommendationEngine
from .storage import ModelDownloadManager, ModelStorage


class ModelManager:
    """Aggregate provider-neutral model discovery and recommendations."""

    def __init__(self, locations: Iterable[Path | str] | None = None, providers: Iterable[ModelProvider] | None = None, storage_root: Path | str | None = None):
        model_root = Path(storage_root or os.environ.get("PROMETHEAN_MODEL_DIR", "/data/models")).expanduser()
        self.storage = ModelStorage(model_root)
        self.downloads = ModelDownloadManager(self.storage)
        self.compatibility = HardwareCompatibilityEngine()
        self.locations = [Path(path).expanduser() for path in (locations or (model_root, "~/.cache/huggingface", "~/.ollama", "/var/lib/ollama"))]
        self.providers = list(providers or (HuggingFaceProvider(), OllamaProvider(), FilesystemModelProvider()))
        self.recommendation_engine = RecommendationEngine()

    def discover(self) -> list[ModelMetadata]:
        models: list[ModelMetadata] = []
        for provider in self.providers:
            models.extend(provider.discover(self.locations))
        return models

    def installed(self) -> list[dict[str, Any]]:
        return self.storage.list_files()

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        provider = next((item for item in self.providers if isinstance(item, HuggingFaceProvider)), HuggingFaceProvider())
        hardware = self.compatibility.current_hardware()
        results = []
        for model in provider.search(query, limit):
            item = model.to_dict()
            item["compatibility"] = self.compatibility.assess(item, hardware)
            results.append(item)
        return results

    def download(self, repository_id: str, filename: str, expected_size: int | None = None) -> dict[str, Any]:
        try:
            existing = self.storage.existing(repository_id, filename)
        except ValueError as exc:
            return {"status": "rejected", "error": str(exc)}
        if existing:
            return {"status": "already_installed", "destination": str(existing), "size_bytes": existing.stat().st_size}
        estimate = self.compatibility.assess({"file_size_bytes": expected_size, "name": repository_id}, self.compatibility.current_hardware())
        if estimate["category"] in {"Unsupported", "Not Recommended"}:
            return {"status": "rejected", "error": f"model is {estimate['category']}", "compatibility": estimate}
        result = self.downloads.start(repository_id, filename, expected_size)
        if result.get("status") == "rejected":
            return result
        return {**result, "compatibility": estimate}

    def download_status(self, job_id: str) -> dict[str, Any] | None:
        return self.downloads.get(job_id)

    def cancel_download(self, job_id: str) -> dict[str, Any] | None:
        return self.downloads.cancel(job_id)

    def delete_installed(self, path: str) -> dict[str, Any]:
        try:
            deleted = self.storage.delete(path)
        except (OSError, ValueError):
            return {"ok": False, "error": "invalid model path"}
        return {"ok": deleted, "error": None if deleted else "model file not found"}

    def launch(self, model_name: str) -> dict[str, Any]:
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

    def recommend(self, metadata: ModelMetadata, hardware: dict[str, Any], runtime: dict[str, Any] | None = None, profile: str = "balanced") -> dict[str, Any]:
        return self.recommendation_engine.recommend(hardware, metadata, runtime, profile)