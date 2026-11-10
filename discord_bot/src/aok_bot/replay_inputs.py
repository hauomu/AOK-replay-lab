"""Bounded replay ingestion; only request-owned staging files are removed."""
from __future__ import annotations

import hashlib
import os
import stat
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


class ReplayInputError(ValueError):
    pass


@dataclass(frozen=True)
class ReplayLimits:
    upload_bytes: int = 25 * 1024 * 1024
    replay_bytes: int = 25 * 1024 * 1024
    expanded_bytes: int = 100 * 1024 * 1024
    zip_entries: int = 200
    replay_members: int = 20
    ratio: int = 200

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in vars(self).values()):
            raise ValueError("Replay limits must be positive integers")


DEFAULT_LIMITS = ReplayLimits()
CHUNK = 64 * 1024


def _digest(stream) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(CHUNK):
        digest.update(chunk)
    return digest.hexdigest()


def stable_copy_name(path: Path) -> str:
    with path.open("rb") as src:
        return _digest(src) + ".SC2Replay"


def _check_member(member, limits):
    name = member.filename.replace("\\", "/")
    if (PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive
            or ".." in name.split("/") or "\x00" in name):
        raise ReplayInputError("Unsafe ZIP path")
    if stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
        raise ReplayInputError("Links and encrypted ZIP entries are unsupported")
    if member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise ReplayInputError("Unsupported ZIP compression")
    if name.lower().endswith(".sc2replay") and not member.is_dir():
        if not 0 < member.file_size <= limits.replay_bytes:
            raise ReplayInputError("Invalid replay size")
        if member.file_size > max(1, member.compress_size) * limits.ratio:
            raise ReplayInputError("ZIP expansion ratio exceeded")
        return True
    return False


def _scan_zip_directory(source, limits):
    """Bound directory allocation before ZipFile builds its ZipInfo table."""
    size = source.seek(0, os.SEEK_END)
    if not 0 < size <= limits.upload_bytes:
        raise ReplayInputError("Invalid upload size")
    source.seek(max(0, size - (65535 + 22)))
    tail = source.read(65535 + 22)
    end = tail.rfind(b"PK\x05\x06")
    if end < 0 or len(tail) - end < 22:
        raise ReplayInputError("Missing ZIP directory end")
    _, disk, cd_disk, disk_count, count, cd_size, cd_offset, comment = struct.unpack_from(
        "<4s4H2IH", tail, end)
    end_offset = size - len(tail) + end
    if (end + 22 + comment != len(tail) or disk or cd_disk or disk_count != count
            or count == 0xffff or cd_size == 0xffffffff or cd_offset == 0xffffffff):
        raise ReplayInputError("Malformed, multidisk or ZIP64 archive")
    if end_offset >= 20:
        source.seek(end_offset - 20)
        if source.read(4) == b"PK\x06\x07":
            raise ReplayInputError("ZIP64 archives are unsupported")
    # Appended/self-extracting ZIPs can have a prefix absent from stored offsets.
    start = end_offset - cd_size
    if start < 0 or cd_offset > start:
        raise ReplayInputError("Invalid ZIP directory range")
    position, actual = start, 0
    while position < end_offset:
        if end_offset - position < 46:
            raise ReplayInputError("Truncated ZIP directory")
        source.seek(position)
        header = source.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise ReplayInputError("Invalid ZIP directory record")
        actual += 1
        if actual > limits.zip_entries:
            raise ReplayInputError("Too many ZIP entries")
        name, extra, note, member_disk = struct.unpack_from("<4H", header, 28)
        compressed, expanded = struct.unpack_from("<2I", header, 20)
        offset = struct.unpack_from("<I", header, 42)[0]
        position += 46 + name + extra + note
        if (position > end_offset or member_disk or compressed == 0xffffffff
                or expanded == 0xffffffff or offset == 0xffffffff):
            raise ReplayInputError("Malformed, multidisk or ZIP64 directory record")
    if actual != count:
        raise ReplayInputError("ZIP entry count mismatch")


def extract_replay_paths(input_path: Path, replays_dir: Path,
                         limits: ReplayLimits = DEFAULT_LIMITS) -> list[Path]:
    suffix = input_path.suffix.lower()
    if suffix not in (".zip", ".sc2replay"):
        raise ReplayInputError("Unsupported input type")
    if not 0 < input_path.stat().st_size <= limits.upload_bytes:
        raise ReplayInputError("Invalid upload size")
    staged = []
    total = 0

    def stage(src, declared=None):
        nonlocal total
        fd, name = tempfile.mkstemp(prefix=".ingest-", dir=replays_dir)
        path = Path(name)
        staged.append((path, None))
        digest, size = hashlib.sha256(), 0
        with os.fdopen(fd, "wb") as dst:
            while chunk := src.read(CHUNK):
                size += len(chunk)
                total += len(chunk)
                if size > limits.replay_bytes or total > limits.expanded_bytes:
                    raise ReplayInputError("Expanded byte limit exceeded")
                dst.write(chunk)
                digest.update(chunk)
        if size == 0 or (declared is not None and size != declared):
            raise ReplayInputError("Invalid expanded size")
        staged[-1] = (path, digest.hexdigest())

    # Preflight the entire directory before creating staging files.
    try:
        if suffix == ".zip":
            with input_path.open("rb") as source:
                _scan_zip_directory(source, limits)
                with zipfile.ZipFile(source) as archive:
                    entries = archive.infolist()
                    if len(entries) > limits.zip_entries:
                        raise ReplayInputError("Too many ZIP entries")
                    selected = [m for m in entries if _check_member(m, limits)]
                    if len(selected) > limits.replay_members:
                        raise ReplayInputError("Too many replay members")
                    if sum(m.file_size for m in selected) > limits.expanded_bytes:
                        raise ReplayInputError("Expanded byte limit exceeded")
                    replays_dir.mkdir(parents=True, exist_ok=True)
                    for member in selected:
                        with archive.open(member) as src:
                            stage(src, member.file_size)
        else:
            if input_path.stat().st_size > min(limits.replay_bytes, limits.expanded_bytes):
                raise ReplayInputError("Replay byte limit exceeded")
            replays_dir.mkdir(parents=True, exist_ok=True)
            with input_path.open("rb") as src:
                stage(src)
        found = []
        for path, digest in staged:
            out = replays_dir / (digest + ".SC2Replay")
            try:
                os.link(path, out)  # Atomic no-replace publication, including concurrent writers.
            except FileExistsError:
                with out.open("rb") as existing:
                    if _digest(existing) != digest:
                        raise ReplayInputError("Cache integrity check failed")
                os.utime(out)  # cache hit: keep it clear of the age-based sweep
            if out not in found:
                found.append(out)
        return found
    except (zipfile.BadZipFile, EOFError, RuntimeError) as exc:
        raise ReplayInputError("Corrupt or unsupported archive") from exc
    finally:
        for path, _ in staged:
            path.unlink(missing_ok=True)
