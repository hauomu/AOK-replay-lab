# SESSION_HANDOFF — AoK Replay Lab

History, newest first. About 10 entries; older ones move to `SESSION_HANDOFF_ARCHIVE.md`.

> Last verified: 2026-11-10 by Claude Opus 5.5.

## 2026-11-10 (SGT) — Claude Code session: SC2 patch fix through charts

- PRs merged and deployed to Tomo (all `[skip ci]`, 0 CI runs): #9 build 98310 decoder, #10 derived gather rates, #11 corpus fixes (both-Win, starting stock, leavers), #12 likely winner from leaves, #13 real-time clock (22.4 loops/s), #14 Astra review fixes (results, PvP attribution, peaks, embeds, mining), #15 market trades + file cleanup (first sweep deleted 70 old files, approved), #16 iron spent from map cost tables. Each deploy backed up the DB (`~/aok-bot/data/backups/`).
- Verified with a 269-replay corpus checker (`outputs/corpus_check_*.jsonl`) per round; validation of iron pricing in `outputs/validate_spent.csv`.
- Astra review (real, via Codex plugin, gpt-6-astra confirmed in rollout): `outputs/astra_review_codex.md`. An earlier "Astra" review via an ocx agent actually ran on Haiku: `outputs/astra_review.md` (treat as unverified).
- Backlog + TwoDie requests written: `outputs/aok_remaining_work_and_twodie_requests.md`.
- Unshipped at handoff: branch `spending-charts-fights` 93f8956 — see `NEXT_WORK.md` item 1.
