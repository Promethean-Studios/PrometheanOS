from pathlib import Path
import pytest

from src.system.models.storage import ModelDownloadManager, ModelStorage


class FakeResponse:
    headers = {"Content-Length": "11"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size):
        if not hasattr(self, "read_count"):
            self.read_count = 0
        self.read_count += 1
        return b"hello world" if self.read_count == 1 else b""


def test_storage_rejects_paths_outside_model_root(tmp_path):
    storage = ModelStorage(tmp_path)

    with pytest.raises(ValueError):
        storage._destination("../other", "model.gguf")
    with pytest.raises(ValueError):
        storage._destination("owner/model", "../model.gguf")


def test_download_writes_real_bytes_and_detects_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr("src.system.models.storage.urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse())
    manager = ModelDownloadManager(ModelStorage(tmp_path))

    result = manager.start("owner/model", "model.gguf", 11)
    import time

    deadline = time.time() + 2
    status = manager.get(result["job_id"])
    while status["status"] not in {"completed", "failed"} and time.time() < deadline:
        time.sleep(0.01)
        status = manager.get(result["job_id"])

    assert status["status"] == "completed"
    destination = Path(status["destination"])
    assert destination.read_bytes() == b"hello world"
    duplicate = manager.start("owner/model", "model.gguf", 11)
    assert duplicate["status"] == "already_installed"


def test_disk_space_can_reject_large_download(tmp_path, monkeypatch):
    storage = ModelStorage(tmp_path)
    monkeypatch.setattr(storage, "disk_space", lambda: {"free_bytes": 10, "total_bytes": 10, "used_bytes": 0})

    result = ModelDownloadManager(storage).start("owner/model", "large.gguf", 11)

    assert result["status"] == "rejected"
    assert result["error"] == "insufficient disk space"
