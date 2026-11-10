# NEXT_WORK — AoK Replay Lab

What is left. Prune closed items (record closures in `SESSION_HANDOFF.md`).

> Last verified: 2026-11-10 19:05 SGT by Claude Opus 5.5. Full backlog with reasoning: `outputs/aok_remaining_work_and_twodie_requests.md`.

## Open

1. **Watch the first real Discord upload on PR #17** — confirm the chart attaches and shows in the embed, and the report/chart files are deleted after sending (`~/aok-bot/data/reports` stays empty).
2. **Same-name players merge in profiles** — needs Battle.net account id from replay details and a DB schema migration (back up first).
3. **Stale stored history** — rows from before the fixes keep old durations/results; consider `/aok_reanalyze` or a parser-version column.
4. **DB backups grow one per deploy** — cap to last N (needs user OK; deleting files).
5. Remaining backlog items B5-B15 and features in Part C of the backlog file.

## Deliberately not doing

- Never remove or hide iron (user ban, 2026-11-10). Missing iron data is derived or requested from TwoDie, not dropped.
- No `ocx-*` agents; Codex models go through the Codex plugin (hook `~/.claude/hooks/ocx_agent_guard.py` enforces it).
- Food is supply, not a spendable resource; it stays out of the spending breakdown.
