from __future__ import annotations

import shutil
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class DownloadJob:
    job_id: str
    repo_id: str
    filename: str
    destination: Path
    total_bytes: Optional[int] = None
    downloaded_bytes: int = 0
    status: str = "queued"
    error: Optional[str] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)

    def to_dict(self) -> Dict[str, Any]:
        progress = None
        if self.total_bytes:
            progress = round(self.downloaded_bytes / self.total_bytes * 100, 2)
        return {
            "job_id": self.job_id,
            "repo_id": self.repo_id,
            "filename": self.filename,
            "destination": str(self.destination),
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "progress_percent": progress,
            "status": self.status,
            "error": self.error,
        }


class ModelStorage:
    """Manage model files without executing or loading downloaded content."""

    EXTENSIONS = {".gguf", ".ggml", ".safetensors", ".bin", ".pt", ".onnx", ".pth"}

    def __init__(self, root: Optional[Path | str] = None):
        requested = Path(root or "/data/models").expanduser().resolve()
        try:
            requested.mkdir(parents=True, exist_ok=True)
            self.root = requested
        except OSError:
            self.root = (Path.home() / ".local" / "share" / "promethean" / "models").resolve()
            self.root.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> list[Dict[str, Any]]:
        files = []
        try:
            paths = (path for path in self.root.rglob("*") if path.is_file() and path.suffix.lower() in self.EXTENSIONS)
            for path in paths:
                try:
                    stat = path.stat()
                except OSError:
                    continue
                files.append({"name": path.stem, "filename": str(path.relative_to(self.root)), "path": str(path), "size_bytes": stat.st_size, "format": path.suffix.lower().lstrip(".")})
        except OSError:
            return []
        return files

    def disk_space(self) -> Dict[str, Optional[int]]:
        try:
            usage = shutil.disk_usage(self.root)
            return {"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}
        except OSError:
            return {"total_bytes": None, "used_bytes": None, "free_bytes": None}

    def existing(self, repo_id: str, filename: str) -> Optional[Path]:
        path = self._destination(repo_id, filename)
        return path if path.is_file() else None

    def delete(self, path: str) -> bool:
        candidate = Path(path).expanduser().resolve()
        candidate.relative_to(self.root)
        if not candidate.is_file():
            return False
        candidate.unlink()
        return True

    def _destination(self, repo_id: str, filename: str) -> Path:
        repo_parts = repo_id.split("/")
        if not repo_id or any(part in {"", ".", ".."} for part in repo_parts):
            raise ValueError("invalid model repository")
        safe_repo = Path(*repo_parts)
        safe_name = Path(filename)
        if safe_name.is_absolute() or ".." in safe_name.parts or not safe_name.name:
            raise ValueError("invalid model filename")
        destination = (self.root / safe_repo / safe_name).resolve()
        destination.relative_to(self.root)
        return destination


class ModelDownloadManager:
    """Download model artifacts in background threads with resumable-safe staging."""

    def __init__(self, storage: ModelStorage):
        self.storage = storage
        self._jobs: Dict[str, DownloadJob] = {}
        self._lock = threading.Lock()

    def start(self, repo_id: str, filename: str, expected_size: Optional[int] = None) -> Dict[str, Any]:
        destination = self.storage._destination(repo_id, filename)
        if destination.is_file():
            return {"status": "already_installed", "destination": str(destination), "size_bytes": destination.stat().st_size}
        space = self.storage.disk_space().get("free_bytes")
        if isinstance(space, int) and isinstance(expected_size, int) and expected_size > space:
            return {"status": "rejected", "error": "insufficient disk space", "free_bytes": space, "required_bytes": expected_size}
        job = DownloadJob(str(uuid.uuid4()), repo_id, filename, destination, expected_size)
        with self._lock:
            self._jobs[job.job_id] = job
        threading.Thread(target=self._download, args=(job,), daemon=True).start()
        return job.to_dict()

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    def cancel(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return None
        job.cancel_event.set()
        return job.to_dict()

    def _download(self, job: DownloadJob) -> None:
        partial = job.destination.with_name(f".{job.destination.name}.{job.job_id}.part")
        try:
            job.destination.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(f"https://huggingface.co/{job.repo_id}/resolve/main/{job.filename}", headers={"User-Agent": "PrometheanOS/0.1"})
            with urllib.request.urlopen(request, timeout=30) as response, partial.open("wb") as output:
                job.status = "downloading"
                if job.total_bytes is None:
                    header = response.headers.get("Content-Length")
                    job.total_bytes = int(header) if header and header.isdigit() else None
                while True:
                    if job.cancel_event.is_set():
                        job.status = "cancelled"
                        return
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    job.downloaded_bytes += len(chunk)
            if job.cancel_event.is_set():
                job.status = "cancelled"
                return
            partial.replace(job.destination)
            job.status = "completed"
        except (OSError, urllib.error.URLError, ValueError) as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            if job.status != "completed":
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    pass
