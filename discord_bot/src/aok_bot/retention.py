"""Age-based cleanup of the bot's scratch folders.

Only regular files directly inside the uploads, reports and replay-cache
folders are touched; the database, backups and dependency folders never are.

- uploads: temporary downloads; each job deletes its own, older ones are leftovers.
- reports: attached to the Discord reply, then deleted; older ones are leftovers.
- replays: content-addressed cache used for re-uploads; kept REPLAY_CACHE_DAYS.
  A cache hit refreshes the file's mtime (replay_inputs), so an in-use replay
  is never old.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

SCRATCH_MAX_AGE_SECONDS = 24 * 3600


@dataclass
class SweepResult:
    uploads: int = 0
    reports: int = 0
    replays: int = 0

    def total(self) -> int:
        return self.uploads + self.reports + self.replays


def _sweep_dir(folder: Path, max_age_seconds: float, now: float, pattern: str = "*") -> int:
    removed = 0
    if not folder.is_dir():
        return 0
    for path in folder.glob(pattern):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            if now - path.stat().st_mtime <= max_age_seconds:
                continue
            path.unlink()
            removed += 1
        except FileNotFoundError:
            continue
        except OSError:
            continue  # never let cleanup break a job
    return removed


def sweep(uploads_dir: Path, reports_dir: Path, replays_dir: Path, replay_cache_days: int,
          now: float | None = None) -> SweepResult:
    now = time.time() if now is None else now
    return SweepResult(
        uploads=_sweep_dir(uploads_dir, SCRATCH_MAX_AGE_SECONDS, now),
        reports=_sweep_dir(reports_dir, SCRATCH_MAX_AGE_SECONDS, now),
        replays=_sweep_dir(replays_dir, replay_cache_days * 86400, now, "*.SC2Replay")
        + _sweep_dir(replays_dir, SCRATCH_MAX_AGE_SECONDS, now, ".ingest-*"),
    )
