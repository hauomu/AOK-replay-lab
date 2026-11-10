# NEXT_WORK — AoK Replay Lab

What is left. Prune closed items (record closures in `SESSION_HANDOFF.md`).

> Last verified: 2026-11-10 19:25 SGT by Claude Opus 5.5. Full backlog with reasoning: `outputs/aok_remaining_work_and_twodie_requests.md`.

## Open

1. **Duplicate games (branch `fix/duplicate-games`)** — code + tests done, not pushed. `replays.game_key` = lobby seed + accounts; a new copy replaces the stored game. After deploy, run `scripts/backfill_account_ids.py --apply` on the live DB (dry run on a copy: 13 keys, drops replay 12, the older copy of replay 13). Needs user OK; DB backup first.
2. **Stale stored history** — rows from before the fixes keep old durations/results; consider `/aok_reanalyze` or a parser-version column.
3. **DB backups grow one per deploy** — cap to last N (needs user OK; deleting files).
4. Remaining backlog items B5-B15 and features in Part C of the backlog file.

## Deliberately not doing

- Never remove or hide iron (user ban, 2026-11-10). Missing iron data is derived or requested from TwoDie, not dropped.
- No `ocx-*` agents; Codex models go through the Codex plugin (hook `~/.claude/hooks/ocx_agent_guard.py` enforces it).
- Food is supply, not a spendable resource; it stays out of the spending breakdown.
