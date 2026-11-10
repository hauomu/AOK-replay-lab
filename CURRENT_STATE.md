# CURRENT_STATE — AoK Replay Lab

What is true now, so a future session does not have to rediscover it. Rewritten in place; history lives in `SESSION_HANDOFF.md`, reasons in `DECISIONS.md`.

> Last verified: 2026-11-10 19:25 SGT by Claude Opus 5.5 (Claude Code). Read `NEXT_WORK.md` next.

## Where things are

- **Repo:** `C:\Users\Sherman\Projects\AOK-replay-lab` (GitHub `hauomu/AOK-replay-lab`, default branch `main`). The older copy at `Desktop\Portfolio\aok-replay-lab` is not a git checkout; don't use it.
- **Live bot:** Tomo, `~/aok-bot` (git checkout of `main`), container `aok-replay-bot`, deployed with `bash scripts/deploy_tomo.sh` (backs up the SQLite DB to `data/backups/` first, pulls `main`, rebuilds, restarts). Discord bot name "AoK FourDie Companion Bot". Secrets in `~/aok-bot/.env` (never read).
- **Live revision:** `81528cb` (PR #18: players identified by Battle.net account), deployed 2026-11-10 19:17 SGT (backup `aok_bot-20261110T111726Z.sqlite3`); live DB backfilled (76 of 145 player rows have `account_id`). Before that `229d0d1` (PR #17: spending breakdown, biggest fights, food supply, timeline chart), deployed 19:01 SGT. First real Discord upload verified 19:06 SGT (replay 34): parsed, saved, chart shown in the embed (user-confirmed), report/chart/upload files deleted after sending. Corpus results for it: `outputs/corpus_check_final.jsonl`; sample report + chart for the user's own upload: `outputs/upload_test/`.
- **Discord upload cache on Tomo:** `~/aok-bot/data/replays/` (root-owned, 30-day sweep).
- **Local test replays:** `C:\Users\Sherman\Documents\StarCraft II\Accounts\250707847\2-S2-1-8333926\Replays\Multiplayer` (269 AoK replays). A copy is on Tomo at `/tmp/aokcorpus` (temporary).
- **Corpus checker:** `outputs/corpus_check.py <dir> <out.jsonl>`, run inside a throwaway `docker run --rm` of the built image on Tomo (~10 min for 269 replays). Never `docker exec`/stop the live `aok-replay-bot`.

## Verified working (live)

- Replays from SC2 build 98310 parse (s2protocol pinned to Blizzard's 98310 release in `discord_bot/Dockerfile`).
- Game time uses the replay's speed: 22.4 loops/s at Faster (`LOOPS_PER_SECOND_BY_SPEED` in `replay_parser.py`).
- Results: recorded Win/Loss kept; contradictory "Win on both sides" dropped; leave-based inference; "Likely win/loss" from who left (validated on 71 labelled games); losing side gets Loss when one side is recorded Win.
- PvP counts only hostile kills; non-PvP deaths in `other_losses`.
- Gather rates derived from gathered-estimate deltas (AoK leaves SC2 CollectionRate at 0); starting stock and clear market trades excluded.
- **Iron = SC2 Terrazine.** Stockpile/income are not in replays (n/a). **Iron spent** is priced from per-map-version cost tables `discord_bot/src/aok_bot/data/aok_costs.json`, built by `scripts/extract_aok_costs.py` from the local Battle.net cache (70 versions, 56 price sets; Legacy and official map differ). Validated: priced gold/wood vs recorded spending median 1.00 (IQR 0.95-1.03).
- Cleanup: reports deleted after sending; sweep of uploads/reports >1 day, replay cache >30 days (`REPLAY_CACHE_DAYS`).

## Also live since PR #17

- Spending breakdown per player/side (Army / Economy / Buildings & defense / Research / Ages; gold/wood/iron) using the map's CostCategory.
- Biggest fights: hostile deaths clustered by >25 s gaps, ranked by value swing, exact start/end + heaviest-minute timestamps.
- **Food = supply** (user's definition): FoodUsed/FoodMade from the replay (/4096); used vs house cap, peak, time supply-capped (house cap or lobby population limit, inferred from peak food in use, options 100-400), cap lost to destroyed houses.
- Timeline chart PNG (matplotlib, added to `requirements.txt`): gather + iron spent/min, army value alive, food used vs cap; fights shaded; attached per report (first five) and in the embed.

## Limitations

- Iron stockpile/income and market trade detail need map changes (see `outputs/aok_remaining_work_and_twodie_requests.md`, Part A).
- Stored DB history predates fixes. Players are grouped by Battle.net account; 11 old replays (other people's uploads, not in the local corpus) have no account ids and fall back to name.
- 7 map versions missing from the local cache use fallback prices (~10% low).

## How to run tests

- Locally: `.venv\Scripts\python -m unittest discover -s tests` (the venv has mpyq, s2protocol, matplotlib).
- On Tomo: build an image from a tarball of `discord_bot tests strategy_mining/src` into `/tmp/aokbuild`, then `docker run --rm ... python -m unittest discover -s tests` with `PYTHONPATH=/app/src:/app/strategy_mining/src`.
