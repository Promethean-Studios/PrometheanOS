from __future__ import annotations

import json
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .metadata import ModelMetadata


class ModelProvider(ABC):
    name = "unknown"

    @abstractmethod
    def discover(self, locations: Iterable[Path]) -> List[ModelMetadata]:
        raise NotImplementedError

    def search(self, query: str, limit: int = 20) -> List[ModelMetadata]:
        return []


def _integer(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _format_for(path: Path) -> Optional[str]:
    formats = {".gguf": "gguf", ".ggml": "ggml", ".safetensors": "safetensors", ".bin": "pytorch", ".pt": "pytorch", ".onnx": "onnx"}
    return formats.get(path.suffix.lower())


class FilesystemModelProvider(ModelProvider):
    name = "filesystem"
    extensions = {".gguf", ".ggml", ".safetensors", ".bin", ".pt", ".onnx"}

    def discover(self, locations: Iterable[Path]) -> List[ModelMetadata]:
        models: List[ModelMetadata] = []
        for location in locations:
            if not location.is_dir():
                continue
            try:
                files = [path for path in location.rglob("*") if path.is_file() and path.suffix.lower() in self.extensions]
            except OSError:
                continue
            for path in files:
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                models.append(ModelMetadata(name=path.stem, provider=self.name, model_format=_format_for(path), file_size_bytes=size, download_size_bytes=size, local_path=str(path)))
        return models


class HuggingFaceProvider(ModelProvider):
    name = "huggingface"

    def search(self, query: str, limit: int = 20) -> List[ModelMetadata]:
        params = urllib.parse.urlencode({"search": query, "limit": max(1, min(limit, 100)), "full": "true"})
        request = urllib.request.Request(f"https://huggingface.co/api/models?{params}", headers={"User-Agent": "PrometheanOS/0.1", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        return [self._remote_metadata(item) for item in payload if isinstance(item, dict) and item.get("id")]

    @staticmethod
    def _remote_metadata(data: Dict[str, Any]) -> ModelMetadata:
        files = []
        for sibling in data.get("siblings", []):
            if not isinstance(sibling, dict) or not sibling.get("rfilename"):
                continue
            files.append({"filename": sibling["rfilename"], "size_bytes": _integer(sibling.get("size"))})
        tags = data.get("tags") if isinstance(data.get("tags"), list) else []
        quantization = next((tag for tag in tags if any(token in str(tag).lower() for token in ("q4", "q5", "q8", "int8", "4bit", "8bit"))), None)
        return ModelMetadata(
            name=data.get("id"), author=data.get("author"), provider="huggingface", repository_id=data.get("id"),
            description=data.get("description") if isinstance(data.get("description"), str) else None,
            parameter_count=_integer(data.get("numParameters") or data.get("parameter_count")),
            quantization=quantization, model_format="huggingface", files=files,
            download_size_bytes=sum(item["size_bytes"] for item in files if isinstance(item.get("size_bytes"), int)) or None,
            runtime_compatibility=["transformers"],
        )

    def discover(self, locations: Iterable[Path]) -> List[ModelMetadata]:
        models: List[ModelMetadata] = []
        for location in locations:
            if not location.is_dir():
                continue
            try:
                for config_path in location.rglob("config.json"):
                    if not config_path.is_file():
                        continue
                    data = self._read_json(config_path)
                    if data is not None:
                        models.append(self._metadata(config_path.parent, data))
            except OSError:
                continue
        return models

    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _metadata(self, path: Path, config: Dict[str, Any]) -> ModelMetadata:
        try:
            files = [item for item in path.rglob("*") if item.is_file()]
            size = sum(item.stat().st_size for item in files)
        except OSError:
            size = None
        author = config.get("_name_or_path") if isinstance(config.get("_name_or_path"), str) else None
        architecture = config.get("model_type") if isinstance(config.get("model_type"), str) else None
        return ModelMetadata(name=path.name, author=author, provider=self.name, architecture=architecture, context_length=_integer(config.get("max_position_embeddings")), model_format="huggingface", file_size_bytes=size, download_size_bytes=size, local_path=str(path), runtime_compatibility=["transformers"])


class OllamaProvider(ModelProvider):
    name = "ollama"

    def discover(self, locations: Iterable[Path]) -> List[ModelMetadata]:
        models: List[ModelMetadata] = []
        for location in locations:
            manifest_root = location / "manifests"
            if not manifest_root.is_dir():
                continue
            try:
                for manifest in manifest_root.rglob("*"):
                    if not manifest.is_file():
                        continue
                    data = self._read_json(manifest)
                    if data is None:
                        continue
                    size = self._blob_size(data)
                    models.append(ModelMetadata(name=":/".join(manifest.relative_to(manifest_root).parts), provider=self.name, model_format="ollama", file_size_bytes=size, download_size_bytes=size, local_path=str(manifest), runtime_compatibility=["ollama"]))
            except OSError:
                continue
        return models

    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _blob_size(manifest: Dict[str, Any]) -> Optional[int]:
        sizes = [_integer(item.get("size")) for item in manifest.get("layers", []) if isinstance(item, dict)]
        sizes = [size for size in sizes if size is not None]
        return sum(sizes) if sizes else None