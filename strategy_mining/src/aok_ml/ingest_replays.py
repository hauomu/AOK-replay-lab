from __future__ import annotations

import argparse
from pathlib import Path
from .replay_events import parse_many


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse AoK replay files/ZIPs into CSV datasets.")
    ap.add_argument("inputs", nargs="+", help=".SC2Replay files, replay folders, or ZIP files containing replays")
    ap.add_argument("--out", default="output", help="Output directory, default: output")
    ap.add_argument("--limit", type=int, default=None, help="Optional parse limit for testing")
    ap.add_argument("--write-events", action="store_true", help="Export full unit_events.csv. Can be very large for hundreds of replays.")
    args = ap.parse_args()
    stats = parse_many([Path(x) for x in args.inputs], Path(args.out), limit=args.limit, write_events=args.write_events)
    print("Done:", stats)

if __name__ == "__main__":
    main()
