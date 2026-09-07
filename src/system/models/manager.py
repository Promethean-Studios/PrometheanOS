from __future__ import annotations

import shutil
import subprocess
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .metadata import ModelMetadata
from .providers import FilesystemModelProvider, HuggingFaceProvider, ModelProvider, OllamaProvider
from .recommendations import RecommendationEngine
from .compatibility import HardwareCompatibilityEngine
from .storage import ModelDownloadManager, ModelStorage


class ModelManager:
    """Aggregate provider-neutral model discovery and recommendations."""

    def __init__(self, locations: Optional[Iterable[Path | str]] = None, providers: Optional[Iterable[ModelProvider]] = None, storage_root: Optional[Path | str] = None):
        model_root = Path(storage_root or os.environ.get("PROMETHEAN_MODEL_DIR", "/data/models")).expanduser()
        self.storage = ModelStorage(model_root)
        self.downloads = ModelDownloadManager(self.storage)
        self.compatibility = HardwareCompatibilityEngine()
        self.locations = [Path(path).expanduser() for path in (locations or (model_root, "~/.cache/huggingface", "~/.ollama", "/var/lib/ollama"))]
        self.providers = list(providers or (HuggingFaceProvider(), OllamaProvider(), FilesystemModelProvider()))
        self.recommendation_engine = RecommendationEngine()

    def discover(self) -> List[ModelMetadata]:
        models: List[ModelMetadata] = []
        for provider in self.providers:
            models.extend(provider.discover(self.locations))
        return models

    def installed(self) -> List[Dict[str, Any]]:
        return self.storage.list_files()

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        provider = next((item for item in self.providers if isinstance(item, HuggingFaceProvider)), HuggingFaceProvider())
        hardware = self.compatibility.current_hardware()
        results = []
        for model in provider.search(query, limit):
            item = model.to_dict()
            item["compatibility"] = self.compatibility.assess(item, hardware)
            results.append(item)
        return results

    def download(self, repository_id: str, filename: str, expected_size: Optional[int] = None) -> Dict[str, Any]:
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

    def download_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.downloads.get(job_id)

    def cancel_download(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.downloads.cancel(job_id)

    def delete_installed(self, path: str) -> Dict[str, Any]:
        try:
            deleted = self.storage.delete(path)
        except (OSError, ValueError):
            return {"ok": False, "error": "invalid model path"}
        return {"ok": deleted, "error": None if deleted else "model file not found"}

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