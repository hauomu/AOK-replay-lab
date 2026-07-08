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


def load_settings() -> Settings:
    load_dotenv()

    data_dir = Path(os.getenv("DATA_DIR", "data"))
    database_path = Path(os.getenv("DATABASE_PATH", str(data_dir / "aok_bot.sqlite3")))

    settings = Settings(
        discord_token=os.getenv("DISCORD_TOKEN", "").strip(),
        guild_id=_optional_int(os.getenv("AOK_GUILD_ID")),
        sc2arcade_region_id=int(os.getenv("SC2ARCADE_REGION_ID", "2")),
        sc2arcade_map_id=int(os.getenv("SC2ARCADE_MAP_ID", "131901")),
        database_path=database_path,
        data_dir=data_dir,
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
