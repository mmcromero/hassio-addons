"""Fail-closed validation and extraction of bounded, untrusted tar streams.

This module never executes archive content. Callers must provide a trusted
allowlist and enforce an external wall-clock timeout for blocking pipe reads.
Only regular files and directories are accepted; links and special files fail.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import time

DEFAULT_MAX_FILES = 4096
DEFAULT_MAX_FILE_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_ARCHIVE_BYTES = (
    DEFAULT_MAX_TOTAL_BYTES + DEFAULT_MAX_FILES * 1024 + 1024 * 1024
)
DEFAULT_MAX_ELAPSED_SECONDS = 240
DEFAULT_MAX_MEMBERS = 32768


class ArchiveStreamError(ValueError):
    """A bounded archive was invalid or exceeded its trusted policy."""


def _safe_path(value: str, *, directory: bool = False) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise ArchiveStreamError("unsafe_archive_path")
    if value.startswith("/") or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ArchiveStreamError("unsafe_archive_path")
    if directory and value.endswith("/"):
        value = value[:-1]
    elif value.endswith("/"):
        raise ArchiveStreamError("unsafe_archive_path")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise ArchiveStreamError("unsafe_archive_path") from exc
    if len(encoded) > 255:
        raise ArchiveStreamError("archive_path_too_long")
    parts = value.split("/")
    if (not value or any(part in ("", ".", "..") for part in parts)
            or ":" in parts[0] or len(parts) > 32):
        raise ArchiveStreamError("unsafe_archive_path")
    sensitive = {".git", ".ssh", ".aws", "options.json", "id_rsa", "id_ed25519", ".env"}
    for part in parts:
        if part in sensitive or (part.startswith(".env.") and part != ".env.example"):
            raise ArchiveStreamError("sensitive_archive_path")
    return value


def _path_set(values, *, label: str) -> set[str]:
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise ArchiveStreamError("invalid_" + label)
    result = [_safe_path(value) for value in values]
    if len(result) != len(set(result)):
        raise ArchiveStreamError("duplicate_" + label)
    return set(result)


class _BoundedReader:
    """Count and hash all bytes consumed by tarfile, with a size/time guard."""

    def __init__(self, source, max_bytes: int, deadline: float):
        self.source = source
        self.max_bytes = max_bytes
        self.deadline = deadline
        self.count = 0
        self.digest = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        if size == 0:
            return b""
        chunks = []
        if size is None or size < 0:
            remaining = self.max_bytes - self.count + 1
        else:
            remaining = min(size, self.max_bytes - self.count + 1)
        while remaining > 0:
            if time.monotonic() > self.deadline:
                raise ArchiveStreamError("archive_elapsed_budget_exceeded")
            chunk = self.source.read(remaining)
            if not chunk:
                break
            self.count += len(chunk)
            if self.count > self.max_bytes:
                raise ArchiveStreamError("archive_byte_budget_exceeded")
            self.digest.update(chunk)
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    def readable(self):
        return True

    def seekable(self):
        return False

    def writable(self):
        return False

    def tell(self):
        return self.count

    def close(self):
        # tarfile may close its wrapper; the caller still needs to drain the
        # original bounded reader to account for trailing bytes.
        return None


def _ensure_directory(root: Path, parts: list[str]) -> Path:
    current = root
    for part in parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o700)
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise ArchiveStreamError("archive_path_collision")
    return current


def validate_and_extract_tar(
    source,
    output_dir,
    *,
    allowed_paths,
    required_paths=(),
    executable_paths=(),
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_archive_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
    max_elapsed_seconds: int = DEFAULT_MAX_ELAPSED_SECONDS,
    max_members: int = DEFAULT_MAX_MEMBERS,
) -> dict:
    """Validate a tar stream and atomically extract only allowlisted regular files.

    The caller owns the stream and must enforce an external timeout if reads can
    block (for example, a child process holding a pipe open). This function
    bounds bytes, members, file sizes, total extracted bytes and processing time.
    It writes to a private staging directory and renames it only after success.
    """
    budgets = {
        "max_files": max_files,
        "max_file_bytes": max_file_bytes,
        "max_total_bytes": max_total_bytes,
        "max_archive_bytes": max_archive_bytes,
        "max_elapsed_seconds": max_elapsed_seconds,
        "max_members": max_members,
    }
    if any(type(value) is not int or value <= 0 for value in budgets.values()):
        raise ArchiveStreamError("invalid_archive_budget")
    allowed = _path_set(allowed_paths, label="allowed_paths")
    required = _path_set(required_paths, label="required_paths")
    executable = _path_set(executable_paths, label="executable_paths")
    if not allowed or not required.issubset(allowed) or not executable.issubset(allowed):
        raise ArchiveStreamError("invalid_archive_allowlist")
    if len(allowed) > max_files:
        raise ArchiveStreamError("archive_file_count_exceeded")

    allowed_dirs = set()
    for name in allowed:
        parts = name.split("/")
        for index in range(1, len(parts)):
            allowed_dirs.add("/".join(parts[:index]))

    target = Path(output_dir)
    if not target.is_absolute():
        target = Path.cwd() / target
    if target.name in ("", ".", "..") or ".." in target.parts:
        raise ArchiveStreamError("unsafe_archive_output")
    parent = target.parent
    if not parent.is_dir():
        raise ArchiveStreamError("unsafe_archive_output_parent")
    cursor = parent
    while True:
        if cursor.is_symlink():
            raise ArchiveStreamError("symlink_archive_output_parent")
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    if target.exists() or target.is_symlink():
        raise ArchiveStreamError("archive_output_already_exists")

    deadline = time.monotonic() + max_elapsed_seconds
    reader = _BoundedReader(source, max_archive_bytes, deadline)
    staging = Path(tempfile.mkdtemp(prefix=".fr-archive-", dir=str(parent)))
    os.chmod(staging, 0o700)
    seen_entries = set()
    explicit_dirs = set()
    file_paths = set()
    required_dirs = set()
    records = []
    total_bytes = 0
    member_count = 0

    try:
        with tarfile.open(fileobj=reader, mode="r|", encoding="utf-8", errors="strict") as archive:
            for member in archive:
                member_count += 1
                if member_count > max_members:
                    raise ArchiveStreamError("archive_member_count_exceeded")
                if time.monotonic() > deadline:
                    raise ArchiveStreamError("archive_elapsed_budget_exceeded")
                if member.pax_headers or getattr(member, "sparse", None):
                    raise ArchiveStreamError("unsupported_archive_metadata")
                if member.mode & 0o7000:
                    raise ArchiveStreamError("unsafe_archive_mode")
                if member.linkname:
                    raise ArchiveStreamError("archive_links_not_allowed")

                if member.type == tarfile.DIRTYPE:
                    name = _safe_path(member.name, directory=True)
                    if member.size != 0 or name not in allowed_dirs:
                        raise ArchiveStreamError("unapproved_archive_directory")
                    if name in seen_entries or name in file_paths:
                        raise ArchiveStreamError("duplicate_or_conflicting_archive_path")
                    parts = name.split("/")
                    if any("/".join(parts[:i]) in file_paths for i in range(1, len(parts))):
                        raise ArchiveStreamError("archive_path_collision")
                    explicit_dirs.add(name)
                    seen_entries.add(name)
                    _ensure_directory(staging, parts)
                    continue

                if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE):
                    raise ArchiveStreamError("archive_links_or_special_files_not_allowed")
                name = _safe_path(member.name)
                if name not in allowed:
                    raise ArchiveStreamError("unapproved_archive_file")
                if name in seen_entries or name in explicit_dirs or name in required_dirs:
                    raise ArchiveStreamError("duplicate_or_conflicting_archive_path")
                if type(member.size) is not int or member.size < 0:
                    raise ArchiveStreamError("invalid_archive_file_size")
                if member.size > max_file_bytes:
                    raise ArchiveStreamError("archive_file_budget_exceeded")
                parts = name.split("/")
                if any("/".join(parts[:i]) in file_paths for i in range(1, len(parts))):
                    raise ArchiveStreamError("archive_path_collision")
                if len(file_paths) + 1 > max_files:
                    raise ArchiveStreamError("archive_file_count_exceeded")
                total_bytes += member.size
                if total_bytes > max_total_bytes:
                    raise ArchiveStreamError("archive_total_budget_exceeded")

                parent_dir = _ensure_directory(staging, parts[:-1])
                destination = parent_dir / parts[-1]
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
                payload = archive.extractfile(member)
                if payload is None:
                    raise ArchiveStreamError("archive_member_unreadable")
                try:
                    descriptor = os.open(destination, flags, 0o600)
                except OSError:
                    payload.close()
                    raise
                digest = hashlib.sha256()
                remaining = member.size
                with payload, os.fdopen(descriptor, "wb") as output:
                    while remaining:
                        chunk = payload.read(min(65536, remaining))
                        if not chunk:
                            raise ArchiveStreamError("truncated_archive_member")
                        if output.write(chunk) != len(chunk):
                            raise ArchiveStreamError("archive_output_short_write")
                        digest.update(chunk)
                        remaining -= len(chunk)
                    if payload.read(1):
                        raise ArchiveStreamError("archive_member_size_mismatch")
                    os.fchmod(output.fileno(), 0o755 if name in executable else 0o644)
                file_paths.add(name)
                seen_entries.add(name)
                for index in range(1, len(parts)):
                    required_dirs.add("/".join(parts[:index]))
                records.append({"path": name, "bytes": member.size, "sha256": digest.hexdigest()})

        # tarfile stops at the end markers; drain the source to enforce the
        # archive byte budget and reject hidden non-zero trailing payload.
        while True:
            trailing = reader.read(65536)
            if not trailing:
                break
            if any(trailing):
                raise ArchiveStreamError("nonzero_archive_trailing_data")
        if not file_paths:
            raise ArchiveStreamError("empty_archive")
        if not required.issubset(file_paths):
            raise ArchiveStreamError("required_archive_file_missing")

        os.rename(staging, target)
        return {
            "format": "factory-runner-archive-v1",
            "state": "VALIDATED_NOT_PUBLISHED",
            "files": sorted(records, key=lambda item: item["path"]),
            "file_count": len(records),
            "total_bytes": total_bytes,
            "archive_bytes": reader.count,
            "archive_sha256": reader.digest.hexdigest(),
        }
    except ArchiveStreamError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except (tarfile.TarError, EOFError, UnicodeError, OSError, ValueError) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise ArchiveStreamError("invalid_archive_or_output_io") from exc
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
