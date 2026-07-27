#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="${AOK_REPO_DIR:-$HOME/aok-bot}"
cd "$repo_dir"

if [[ ! -d .git ]]; then
  printf 'Error: %s is not a Git checkout.\n' "$repo_dir" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  printf 'Error: %s/.env is missing.\n' "$repo_dir" >&2
  exit 1
fi

mkdir -p data/backups

if [[ -f data/aok_bot.sqlite3 ]]; then
  backup="data/backups/aok_bot-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
  cp --preserve=mode,timestamps data/aok_bot.sqlite3 "$backup"
  printf 'Database backup: %s\n' "$backup"
fi

git fetch --prune origin
git checkout main
git pull --ff-only origin main

export GIT_COMMIT
GIT_COMMIT="$(git rev-parse HEAD)"

docker compose build --pull
docker compose up --detach --remove-orphans

docker inspect aok-replay-bot \
  --format 'container={{.Name}} status={{.State.Status}} restart={{.HostConfig.RestartPolicy.Name}} revision={{index .Config.Labels "org.opencontainers.image.revision"}}'
docker logs --tail 30 aok-replay-bot
