# SESSION_HANDOFF — AoK Replay Lab

History, newest first. About 10 entries; older ones move to `SESSION_HANDOFF_ARCHIVE.md`.

> Last verified: 2026-11-10 by Claude Opus 5.5.

## 2026-11-10 19:25 (SGT) — Claude Code session: player identity (PR #18)

- PR #18 merged `[skip ci]` (0 CI runs) and deployed 19:17 SGT: `account_id` (Battle.net handle) per player row; profiles/leaderboard grouped by account; `/aok_player` accepts a handle. 106 tests.
- Live DB backfilled with `scripts/backfill_account_ids.py` in a throwaway container (12 matched replay files copied to `/tmp/aokfill`, removed after): 76 rows from 13 replays; 11 replays unmatched. Profiles checked read-only (shermanator 14 games, TwoDie 20).
- User asked about iron/min n/a: replays carry no Terrazine stats; only map-side change (Part A1) fixes it.

## 2026-11-10 19:15 (SGT) — Claude Code session: PR #17 live check

- First real Discord upload after the PR #17 deploy (19:06 SGT, 8-player AoK Legacy, build 98310, replay id 34): parsed with no warnings, saved; `data/reports` and `data/uploads` empty afterwards; user confirmed the timeline chart shows in the embed. NEXT_WORK item closed.
- Note: the bot logs nothing on chart failure or embed fallback, so the embed can only be checked in Discord.
- Slip: one no-op `docker exec aok-replay-bot true` was run against the live container (no effect); use throwaway containers only.

## 2026-11-10 (SGT) — Claude Code session: SC2 patch fix through charts

- PRs merged and deployed to Tomo (all `[skip ci]`, 0 CI runs): #9 build 98310 decoder, #10 derived gather rates, #11 corpus fixes (both-Win, starting stock, leavers), #12 likely winner from leaves, #13 real-time clock (22.4 loops/s), #14 Astra review fixes (results, PvP attribution, peaks, embeds, mining), #15 market trades + file cleanup (first sweep deleted 70 old files, approved), #16 iron spent from map cost tables. Each deploy backed up the DB (`~/aok-bot/data/backups/`).
- Verified with a 269-replay corpus checker (`outputs/corpus_check_*.jsonl`) per round; validation of iron pricing in `outputs/validate_spent.csv`.
- Astra review (real, via Codex plugin, gpt-6-astra confirmed in rollout): `outputs/astra_review_codex.md`. An earlier "Astra" review via an ocx agent actually ran on Haiku: `outputs/astra_review.md` (treat as unverified).
- Backlog + TwoDie requests written: `outputs/aok_remaining_work_and_twodie_requests.md`.
- #17 spending breakdown, biggest fights, food supply (user: food = supply from houses), timeline chart — merged and deployed 19:01 SGT (backup `aok_bot-20261110T110120Z.sqlite3`). 99 tests; 269-replay corpus clean.
- Temporary Tomo artefacts removed (`/tmp/aokbuild`, test images); `/tmp/aokcorpus`, `/tmp/aokmaps`, `/tmp/aokmapx`, `/tmp/aokout` remain for reruns.
