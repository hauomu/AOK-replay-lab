"""Owned decoder subprocess. Bounds resources, but is not an OS security sandbox."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import threading
import types
from collections import Counter
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

if __package__:
    from .models import ReplaySummary
else:  # Isolated child interpreter ignores inherited PYTHONPATH.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from aok_bot.models import ReplaySummary


class ReplayWorkerError(RuntimeError):
    pass


def _encode(value):
    if is_dataclass(value):
        return {f.name: _encode(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Counter):
        return {"__counter__": dict(value)}
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _decode(value, hint):
    origin, args = get_origin(hint), get_args(hint)
    if hint is Any:
        return value  # JSON-only values in timeline snapshots.
    if origin is types.UnionType:
        for option in args:
            try:
                return _decode(value, option)
            except (ValueError, TypeError):
                pass
        raise ValueError("Invalid union value")
    if is_dataclass(hint):
        hints = get_type_hints(hint)
        if not isinstance(value, dict) or set(value) != set(hints):
            raise ValueError("Invalid summary fields")
        return hint(**{k: _decode(v, hints[k]) for k, v in value.items()})
    if origin is list:
        if type(value) is not list:
            raise ValueError("Expected list")
        return [_decode(v, args[0]) for v in value]
    if origin is dict:
        if type(value) is not dict:
            raise ValueError("Expected dictionary")
        counter = set(value) == {"__counter__"}
        source = value["__counter__"] if counter else value
        if type(source) is not dict:
            raise ValueError("Invalid counter")
        result = {_decode(k, args[0]): _decode(v, args[1]) for k, v in source.items()}
        return Counter(result) if counter else result
    if hint is Path and type(value) is str:
        return Path(value)
    if type(value) is not hint:
        raise ValueError("Invalid field type")
    return value


def encode_summary(summary: ReplaySummary) -> bytes:
    return json.dumps({"version": 1, "summary": _encode(summary)},
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def decode_summary(data: bytes) -> ReplaySummary:
    try:
        def reject_constant(value):
            raise ValueError("Non-finite JSON number")
        envelope = json.loads(data, parse_constant=reject_constant)
        if (type(envelope) is not dict or set(envelope) != {"version", "summary"}
                or type(envelope["version"]) is not int or envelope["version"] != 1):
            raise ValueError("Invalid envelope")
        summary = _decode(envelope["summary"], ReplaySummary)
        if summary.parser_ok and (not summary.players or not summary.raw_event_counts):
            raise ValueError("Missing successful analysis data")
        return summary
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as exc:
        raise ReplayWorkerError("Decoder returned malformed analysis") from exc


def child_environment() -> dict[str, str]:
    # No token, proxy, Python startup or application configuration inheritance.
    return {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "TEMP", "TMP") if k in os.environ}


def _run(command, *, deadline: float, output_bytes: int) -> bytes:
    chunks, overflow = [], threading.Event()
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          stdin=subprocess.DEVNULL, env=child_environment()) as process:
        def read_output():
            remaining = output_bytes
            while chunk := process.stdout.read(min(65536, remaining + 1)):
                if len(chunk) > remaining:
                    overflow.set()
                    process.kill()
                    return
                chunks.append(chunk)
                remaining -= len(chunk)
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            process.wait(timeout=deadline)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            reader.join()
            raise ReplayWorkerError("Replay decoding timed out") from exc
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        reader.join()
        if overflow.is_set():
            raise ReplayWorkerError("Decoder output limit exceeded")
        if process.returncode:
            raise ReplayWorkerError("Replay decoder failed")
    return b"".join(chunks)


def parse_replay_isolated(path: Path, *, deadline: float = 65, cpu_seconds: int = 60,
                          memory_bytes: int = 512 * 1024 * 1024,
                          output_bytes: int = 8 * 1024 * 1024) -> ReplaySummary:
    if (type(deadline) not in (int, float) or not 0 < deadline < math.inf
            or any(type(value) is not int or value <= 0
                   for value in (cpu_seconds, memory_bytes, output_bytes))):
        raise ValueError("Worker deadline must be finite and positive; resource caps must be positive integers")
    command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
               str(path.resolve()), str(cpu_seconds), str(memory_bytes)]
    summary = decode_summary(_run(command, deadline=deadline, output_bytes=output_bytes))
    if summary.source_path != path.resolve():
        raise ReplayWorkerError("Decoder returned mismatched replay")
    # Parser errors may contain internal paths or untrusted text; keep bot output generic.
    if not summary.parser_ok:
        summary.warnings = ["Replay analysis failed; no reliable statistics are available."]
    return summary


def _main():
    path, cpu, memory = sys.argv[1:]
    if sys.platform.startswith("linux"):
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (int(cpu), int(cpu)))
        resource.setrlimit(resource.RLIMIT_AS, (int(memory), int(memory)))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "external" / "s2protocol"))
    from aok_bot.replay_parser import parse_replay
    sys.stdout.buffer.write(encode_summary(parse_replay(Path(path))))


if __name__ == "__main__":
    _main()
