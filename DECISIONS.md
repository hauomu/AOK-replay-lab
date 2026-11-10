# DECISIONS — AoK Replay Lab

Why it is this way. Numbered; amend in place, add new entries for reversals.

> Last verified: 2026-11-10 by Claude Opus 5.5.

1. **Iron = SC2 Terrazine; report iron spent, not iron gathered.**
   Why: replays only store Minerals/Vespene stats; the map (confirmed in `MapScript.galaxy`, 142 `c_playerPropTerrazine` uses) keeps iron in Terrazine. Prices come from each map version's own game data.
   Consequence: iron stockpile/income show n/a until the map exposes them (request to TwoDie); never remove iron columns.

2. **Per-map-version cost tables, shipped in the repo.**
   Why: Legacy and the official map price 34 of 62 shared units, plus research and ages, differently; the bot on Tomo cannot see the PC's Battle.net cache.
   Consequence: rerun `scripts/extract_aok_costs.py` when new map versions appear; unknown versions fall back to the newest same-title table and the report says so.

3. **Paid vs free:** units count as bought only when born with a creator ability; buildings at construction start (cancelled refunded); research at completion.
   Why: map spawns (starting peasants, trigger houses) have no creator ability. Validated against recorded gold/wood spending (median 1.00).

4. **Game time = loops / 22.4 at Faster** (speed read per replay). END_EXIT_SECONDS = 11 real seconds keeps the corpus-tuned 15 game-second window.

5. **Results:** recorded single-side Win implies the others lost; Win on several sides names no winner; leave inference and "Likely" results are labelled as such.

6. **Food is supply** (user definition, 2026-11-10): read FoodUsed/FoodMade from the replay; population limit is a lobby option (100-400) inferred from peak food in use.

8. **Player identity = Battle.net account** (2026-11-10): `replay_players.account_id` holds the handle `region-S2-realm-id` from `details.m_toon`. One account is one profile across renames (latest name shown); same-name accounts stay apart and are told apart by handle. Rows without an account id join the single account that used that name, otherwise stand alone under the exact name. Old rows are backfilled by `scripts/backfill_account_ids.py` (match by player-name list + duration).

9. **One stored row per game** (2026-11-10): `replays.game_key` = `m_randomValue` from initData + sorted human account handles. Every copy of a game (renamed file, a teammate's recording) maps to one row; the newest good parse wins. The seed was unique across all 1,264 local replays. Rows without a key are never merged.

7. **Delegation:** Codex models only via the Codex plugin companion; ocx agents are blocked by a PreToolUse hook that redirects them to the plugin.
