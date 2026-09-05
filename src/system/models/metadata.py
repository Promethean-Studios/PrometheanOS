from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ModelMetadata:
    """Normalized model information. None means the source did not provide it."""

    name: Optional[str] = None
    author: Optional[str] = None
    provider: Optional[str] = None
    parameter_count: Optional[int] = None
    architecture: Optional[str] = None
    quantization: Optional[str] = None
    context_length: Optional[int] = None
    model_format: Optional[str] = None
    file_size_bytes: Optional[int] = None
    download_size_bytes: Optional[int] = None
    local_path: Optional[str] = None
    runtime_compatibility: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)