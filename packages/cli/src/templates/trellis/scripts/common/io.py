"""
JSON file I/O utilities.

Provides read_json and write_json as the single source of truth
for JSON file operations across all Trellis scripts.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def read_json(path: Path) -> dict | None:
    """Read and parse a JSON file.

    Returns None if the file doesn't exist, is invalid JSON, or can't be read.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def write_json(path: Path, data: dict) -> bool:
    """Write dict to JSON file with pretty formatting.

    Returns True on success, False on error.
    """
    try:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except (OSError, IOError):
        return False


def write_json_atomic(path: Path, data: dict) -> bool:
    """Atomically replace a JSON file without exposing a partial document."""
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        return True
    except (OSError, IOError, TypeError, ValueError):
        return False
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass


def write_text_atomic(path: Path, text: str, *, mode: int = 0o600) -> bool:
    """Atomically replace a UTF-8 text file and apply a restrictive mode."""
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, mode)
        temporary_path = None
        return True
    except (OSError, IOError, TypeError, ValueError):
        return False
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass


def path_has_symlink(path: Path, root: Path) -> bool:
    """Return True when a repository-relative path crosses a symlink."""
    try:
        root_absolute = root.absolute()
        relative = path.absolute().relative_to(root_absolute)
    except ValueError:
        return True
    current = root_absolute
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive cross-process lock for a task state transition."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.chmod(path, 0o600)
        if os.name == "nt":
            import msvcrt

            if os.path.getsize(path) == 0:
                os.write(descriptor, b"0")
                os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
