from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    guild_id: int | None
    sc2arcade_region_id: int
    sc2arcade_map_id: int
    database_path: Path
    data_dir: Path
    patch_notes_enabled: bool
    patch_notes_channel_id: int | None
    patch_notes_region_id: int
    patch_notes_map_id: int
    patch_notes_locale: str
    patch_notes_poll_minutes: int
    patch_notes_create_discussion_thread: bool
    patch_notes_mention_role_id: int | None
    patch_notes_mention_on_first_import: bool
    patch_notes_edit_existing_posts: bool
    patch_notes_first_run_mode: str

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def replays_dir(self) -> Path:
        return self.data_dir / "replays"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def dependencies_dir(self) -> Path:
        return self.data_dir / "dependencies"


def _optional_int(value: str | None) -> int | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    return int(value)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(name: str, default: int, minimum: int = 1) -> int:
    value = int(os.getenv(name, str(default)))
    return max(minimum, value)


def load_settings() -> Settings:
    load_dotenv()

    data_dir = Path(os.getenv("DATA_DIR", "data"))
    database_path = Path(os.getenv("DATABASE_PATH", str(data_dir / "aok_bot.sqlite3")))
    sc2arcade_region_id = int(os.getenv("SC2ARCADE_REGION_ID", "2"))
    sc2arcade_map_id = int(os.getenv("SC2ARCADE_MAP_ID", "131901"))

    first_run_mode = os.getenv("PATCH_NOTES_FIRST_RUN_MODE", "latest").strip().lower()
    if first_run_mode not in {"baseline", "latest", "all"}:
        raise ValueError(
            "PATCH_NOTES_FIRST_RUN_MODE must be one of: baseline, latest, all"
        )

    settings = Settings(
        discord_token=os.getenv("DISCORD_TOKEN", "").strip(),
        guild_id=_optional_int(os.getenv("AOK_GUILD_ID")),
        sc2arcade_region_id=sc2arcade_region_id,
        sc2arcade_map_id=sc2arcade_map_id,
        database_path=database_path,
        data_dir=data_dir,
        patch_notes_enabled=_env_bool("ENABLE_PATCH_NOTE_WATCHER", False),
        patch_notes_channel_id=_optional_int(os.getenv("PATCH_NOTES_CHANNEL_ID")),
        patch_notes_region_id=int(
            os.getenv("PATCH_NOTES_REGION_ID", str(sc2arcade_region_id))
        ),
        patch_notes_map_id=int(
            os.getenv("PATCH_NOTES_MAP_ID", str(sc2arcade_map_id))
        ),
        patch_notes_locale=os.getenv("PATCH_NOTES_LOCALE", "enUS").strip() or "enUS",
        patch_notes_poll_minutes=_positive_int(
            "PATCH_NOTES_POLL_MINUTES",
            60,
            minimum=5,
        ),
        patch_notes_create_discussion_thread=_env_bool(
            "PATCH_NOTES_CREATE_DISCUSSION_THREAD",
            True,
        ),
        patch_notes_mention_role_id=_optional_int(
            os.getenv("PATCH_NOTES_MENTION_ROLE_ID")
        ),
        patch_notes_mention_on_first_import=_env_bool(
            "PATCH_NOTES_MENTION_ON_FIRST_IMPORT",
            False,
        ),
        patch_notes_edit_existing_posts=_env_bool(
            "PATCH_NOTES_EDIT_EXISTING_POSTS",
            True,
        ),
        patch_notes_first_run_mode=first_run_mode,
    )

    if settings.patch_notes_enabled and settings.patch_notes_channel_id is None:
        raise ValueError(
            "ENABLE_PATCH_NOTE_WATCHER=true requires PATCH_NOTES_CHANNEL_ID"
        )

    for path in [
        settings.data_dir,
        settings.uploads_dir,
        settings.replays_dir,
        settings.reports_dir,
        settings.dependencies_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)

    return settings
