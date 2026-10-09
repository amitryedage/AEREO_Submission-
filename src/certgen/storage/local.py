"""File storage abstraction and local filesystem implementation with atomic writes."""

import os
from pathlib import Path
from typing import BinaryIO, Protocol


class StorageError(Exception):
    """Raised when storage operations fail."""

    pass


class FileStorage(Protocol):
    """Protocol defining the file storage contract."""

    def save(self, key: str, content: bytes) -> None:
        """Atomically persist content to storage at key."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Open binary stream for key."""
        ...

    def exists(self, key: str) -> bool:
        """Check whether key exists in storage."""
        ...

    def get_path(self, key: str) -> Path:
        """Resolve absolute filesystem path for key."""
        ...


class LocalFileStorage:
    """Local filesystem storage with path traversal protection and atomic writes."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        """Resolve target path and verify it stays strictly inside storage root."""
        # Clean relative key
        normalized_key = key.lstrip("/\\")
        target_path = (self.root / normalized_key).resolve()

        try:
            target_path.relative_to(self.root)
        except ValueError as err:
            raise StorageError(f"Path traversal detected: {key}") from err

        return target_path

    def save(self, key: str, content: bytes) -> None:
        """Atomically write bytes to key using temporary file rename."""
        target_path = self._resolve_path(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = target_path.with_name(f"{target_path.name}.tmp")

        try:
            temp_path.write_bytes(content)
            # os.replace provides atomic rename on POSIX and Windows (same volume)
            os.replace(temp_path, target_path)
        except Exception as e:
            if temp_path.exists():
                import contextlib

                with contextlib.suppress(OSError):
                    temp_path.unlink()
            raise StorageError(f"Failed to save file '{key}': {e}") from e

    def open(self, key: str) -> BinaryIO:
        """Open file for reading in binary mode."""
        target_path = self._resolve_path(key)
        if not target_path.is_file():
            raise FileNotFoundError(f"File not found in storage: {key}")
        return open(target_path, "rb")

    def exists(self, key: str) -> bool:
        """Check if file exists and is a regular file."""
        try:
            target_path = self._resolve_path(key)
            return target_path.is_file()
        except StorageError:
            return False

    def get_path(self, key: str) -> Path:
        """Get absolute path for key after traversal check."""
        return self._resolve_path(key)
