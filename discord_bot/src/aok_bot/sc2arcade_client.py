from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp


@dataclass
class ArcadeLobby:
    region_id: int
    bnet_id: int | None
    title: str
    status: str | None
    created_at: str | None
    closed_at: str | None
    raw: dict[str, Any]


class SC2ArcadeClient:
    def __init__(self, user_agent: str = "AoKReplayAnalyzer/1.1"):
        # Important: the public WebAPI host is api.sc2arcade.com, not
        # sc2arcade.com/api. The website fallback remains for older endpoints
        # that may still be proxied through the frontend host.
        self.base_urls = [
            "https://api.sc2arcade.com",
            "https://sc2arcade.com/api",
        ]
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://sc2arcade.com/",
        }

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        last_error: Exception | None = None
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(headers=self.headers, timeout=timeout) as session:
            for base_url in self.base_urls:
                url = f"{base_url}{path}"
                try:
                    async with session.get(url, params=params) as resp:
                        resp.raise_for_status()
                        return await resp.json()
                except Exception as exc:
                    last_error = exc
                    continue
        if last_error is not None:
            raise last_error
        raise RuntimeError("SC2Arcade request failed without an error")

    async def get_recent_lobbies(
        self,
        region_id: int,
        map_id: int,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        params = {
            "regionId": region_id,
            "mapId": map_id,
            "includeMapInfo": "true",
            "includeSlots": "true",
            "includeSlotsProfile": "true",
            "includeMatchResult": "true",
            "includeMatchPlayers": "true",
            "orderDirection": "desc",
            "limit": limit,
        }
        data = await self._get_json("/lobbies/history", params=params)

        if isinstance(data, dict):
            return data.get("results") or data.get("list") or []
        if isinstance(data, list):
            return data
        return []

    async def get_map_details(
        self,
        region_id: int,
        map_id: int,
        *,
        locale: str = "enUS",
        major_version: int = 0,
        minor_version: int = 0,
    ) -> dict[str, Any]:
        """Return rich map metadata, including localized patch-note sections."""

        params: dict[str, Any] = {"locale": locale}
        if major_version:
            params["majorVersion"] = major_version
        if minor_version:
            params["minorVersion"] = minor_version
        data = await self._get_json(
            f"/maps/{region_id}/{map_id}/details",
            params=params,
        )
        if not isinstance(data, dict):
            raise RuntimeError("SC2Arcade map-details response was not a JSON object")
        return data

    async def get_map_versions(self, region_id: int, map_id: int) -> dict[str, Any]:
        data = await self._get_json(f"/maps/{region_id}/{map_id}/versions")
        if not isinstance(data, dict):
            raise RuntimeError("SC2Arcade map-versions response was not a JSON object")
        return data

    async def get_map_dependencies(self, region_id: int, map_id: int) -> dict[str, Any]:
        data = await self._get_json(f"/maps/{region_id}/{map_id}/dependencies")
        if isinstance(data, dict):
            return data
        return {"list": data if isinstance(data, list) else []}
