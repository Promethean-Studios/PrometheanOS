from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ModelMetadata:
    """Normalized model information. None means the source did not provide it."""

    name: str | None = None
    author: str | None = None
    provider: str | None = None
    parameter_count: int | None = None
    architecture: str | None = None
    quantization: str | None = None
    context_length: int | None = None
    model_format: str | None = None
    file_size_bytes: int | None = None
    download_size_bytes: int | None = None
    local_path: str | None = None
    runtime_compatibility: list[str] | None = None
    description: str | None = None
    repository_id: str | None = None
    files: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)