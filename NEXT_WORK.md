# NEXT_WORK — AoK Replay Lab

What is left. Prune closed items (record closures in `SESSION_HANDOFF.md`).

> Last verified: 2026-11-10 18:45 SGT by Claude Opus 5.5. Full backlog with reasoning: `outputs/aok_remaining_work_and_twodie_requests.md`.

## Open

1. **Check and ship branch `spending-charts-fights` (93f8956).**
   - Status: committed, 99 tests pass locally; Tomo corpus run (image `aok-replay-lab:features2`) was running.
   - Why: user asked for spending breakdown, fight timeline, food supply and charts.
   - What to do: compare `outputs/corpus_check_final.jsonl` with `outputs/corpus_check_iron.jsonl` (no crashes, no embed over 6000 chars, no `breakdown_mismatch` or `chart_raised` flags, chart times reasonable); review `outputs/upload_test/` (report + PNG for the user's 17:36 Legacy upload) and send it to the user; then ask approval to push/PR/merge (`[skip ci]`, 0 CI runs) and redeploy with `scripts/deploy_tomo.sh`. Remove image `aok-replay-lab:features2` and `/tmp/aokbuild` afterwards.
2. **Same-name players merge in profiles** — needs Battle.net account id from replay details and a DB schema migration (back up first).
3. **Stale stored history** — rows from before the fixes keep old durations/results; consider `/aok_reanalyze` or a parser-version column.
4. **DB backups grow one per deploy** — cap to last N (needs user OK; deleting files).
5. Remaining backlog items B5-B15 and features in Part C of the backlog file.

## Deliberately not doing

- Never remove or hide iron (user ban, 2026-11-10). Missing iron data is derived or requested from TwoDie, not dropped.
- No `ocx-*` agents; Codex models go through the Codex plugin (hook `~/.claude/hooks/ocx_agent_guard.py` enforces it).
- Food is supply, not a spendable resource; it stays out of the spending breakdown.
