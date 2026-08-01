# Stage 1 — Canonical workspace

- Stage 0A durable record: `/home/sherman/stage0a_canonical_workspace_discovery_20260801-019fb9a5.md`
- Canonical repository: `/srv/projects/medical-dictionary`
- Retained source: `/home/sherman/aok-bot`
- Recovery artifacts:
  - `/home/sherman/stage1-recovery-20260801-019fb9a5/data`
  - `/home/sherman/stage1-recovery-20260801-019fb9a5/.env`
- Actions: created `/srv/projects` as `sherman:sherman` mode 2775; cloned `https://github.com/hauomu/AOK-replay-lab.git`; restored local `agent/docker-deployment` tracking branch; copied ignored `data/` and `.env`; left the source unchanged.
- Validation: passed. Canonical HEAD is `2a78725c6932483aacbf2b5a1429d072ce97cee2` on `main`; origin URL and main upstream match; local and remote branch refs match; source was clean; tracked content, `data/`, and `.env` match; no submodules, LFS files, or symlinks; destination is sherman-owned and `.env` is mode 600.
- Rollback: with separate approval, remove only the canonical destination after validation failure; retain the source and recovery artifacts. Never retire the source without a separate approval.
- Remaining blockers: none for Stage 1. Source retirement and all later architecture stages remain intentionally out of scope.

## Stage 2 — GitHub protection and hosted CI — 2026-08-01

- Repository: `hauomu/AOK-replay-lab`; default branch: `main`.
- Ruleset: ID `20175964`, repository-level target `~DEFAULT_BRANCH`, enforcement `active`, bypass list empty.
- Configured rules: pull requests required; required review-thread resolution; required checks with strict latest-code policy; force-push blocking via `non_fast_forward`; branch deletion blocking. No approving review is required.
- Required successful check names: `requirements (discord_bot)`; `requirements (strategy_mining)`.
- Workflow added: `.github/workflows/stage2-baseline.yml`. It installs the two existing `requirements.txt` files and runs `python -m pip check`; no application commands or dependencies were invented.
- PR: #4, `https://github.com/hauomu/AOK-replay-lab/pull/4`, targeting `main`; human merge remains pending.
- Safe rejection test: passed. A synthetic commit pushed directly to disposable branch `stage2-validation-20260801-1` was rejected with GitHub `GH013` because changes must be made through a pull request. The disposable branch and temporary ruleset target were deleted afterward.
- Rollback: before merge, close PR #4, delete `stage2/ci-and-protection-20260801`, and delete ruleset `20175964`; after merge, revert the workflow/documentation through a new PR and restore the captured ruleset configuration. Never force-push or rewrite `main`.
- Remaining blockers: manual human merge of PR #4. Stage 3 and later work is out of scope.
