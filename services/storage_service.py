"""Filesystem storage for uploads."""
from pathlib import Path

from flask import current_app


class StorageService:
    def root_dir(self) -> Path:
        path = current_app.config["STORAGE_PATH"]
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def absolute_path(self, stored_filename: str) -> Path:
        return self.root_dir() / stored_filename

    def save_bytes(self, stored_filename: str, data: bytes) -> Path:
        dest = self.absolute_path(stored_filename)
        dest.write_bytes(data)
        return dest
