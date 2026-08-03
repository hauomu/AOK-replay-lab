from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

_VERSION_PREFIX_RE = re.compile(r"^\s*(?:version\s*|v\s*)?(.+?)\s*$", re.IGNORECASE)
_VERSION_NUMBER_RE = re.compile(r"\d+")


@dataclass(frozen=True)
class PatchNote:
    """One localized StarCraft II Arcade patch-note section."""

    version: str
    title: str
    published_at: str | None
    items: tuple[str, ...]
    source_order: int

    @property
    def content_hash(self) -> str:
        payload = {
            "version": self.version,
            "title": self.title,
            "published_at": self.published_at,
            "items": list(self.items),
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "title": self.title,
            "published_at": self.published_at,
            "items": list(self.items),
            "source_order": self.source_order,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PatchNote":
        return cls(
            version=str(payload.get("version") or "unknown"),
            title=str(payload.get("title") or "Patch notes"),
            published_at=_clean_optional_text(payload.get("published_at")),
            items=tuple(_normalise_items(payload.get("items"))),
            source_order=int(payload.get("source_order") or 0),
        )


def extract_patch_notes(payload: dict[str, Any]) -> list[PatchNote]:
    """Extract patch-note sections from an SC2Arcade map-details response.

    SC2Arcade's public schema has historically described ``patchNoteSections``
    as a single object, while live responses may expose either an object or an
    array. This parser intentionally accepts both shapes and a small number of
    wrapper variants so the bot fails closed instead of publishing malformed
    notes when the upstream representation changes.
    """

    arcade_info = (
        payload.get("info", {}).get("arcadeInfo", {})
        if isinstance(payload.get("info"), dict)
        else {}
    )
    raw_sections = arcade_info.get("patchNoteSections")

    sections = _as_sections(raw_sections)
    notes: list[PatchNote] = []

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue

        title = _clean_optional_text(
            section.get("title")
            or section.get("versionTitle")
            or section.get("name")
        ) or "Patch notes"
        published_at = _clean_optional_text(
            section.get("subtitle")
            or section.get("publishedAt")
            or section.get("date")
        )
        items = tuple(
            _normalise_items(
                section.get("items")
                or section.get("notes")
                or section.get("lines")
            )
        )

        version = _extract_version(
            section.get("version")
            or section.get("versionName")
            or title
        )
        if not version:
            # Stable fallback for unusual upstream entries without a version.
            version = f"entry-{index + 1}"

        # Ignore fully empty placeholder sections.
        if title == "Patch notes" and not published_at and not items:
            continue

        notes.append(
            PatchNote(
                version=version,
                title=title,
                published_at=published_at,
                items=items,
                source_order=index,
            )
        )

    # The Arcade normally returns newest first. Sorting by parsed version makes
    # the result deterministic if the upstream source changes order. Re-number
    # source_order after sorting so zero always means the latest known entry.
    ordered = sorted(notes, key=_note_sort_key, reverse=True)
    return [
        PatchNote(
            version=note.version,
            title=note.title,
            published_at=note.published_at,
            items=note.items,
            source_order=index,
        )
        for index, note in enumerate(ordered)
    ]


def latest_patch_note(notes: Iterable[PatchNote]) -> PatchNote | None:
    materialised = list(notes)
    if not materialised:
        return None
    return max(materialised, key=_note_sort_key)


def format_patch_note_body(note: PatchNote) -> str:
    """Return Discord-flavoured Markdown while preserving source wording."""

    if not note.items:
        return "_No detailed notes were provided for this version._"

    lines: list[str] = []
    for item in note.items:
        text = item.strip()
        if not text:
            continue
        if text.startswith(("•", "-", "*")):
            lines.append(text)
        else:
            lines.append(f"• {text}")
    return "\n".join(lines) or "_No detailed notes were provided for this version._"


def _as_sections(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if isinstance(raw, dict):
        # Some APIs wrap the actual list under a generic key.
        for key in ("sections", "results", "list", "entries"):
            wrapped = raw.get(key)
            if isinstance(wrapped, list):
                return [item for item in wrapped if isinstance(item, dict)]
        return [raw]

    return []


def _normalise_items(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [line.strip() for line in raw.splitlines() if line.strip()]
    if not isinstance(raw, list):
        return [str(raw).strip()] if str(raw).strip() else []

    result: list[str] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("text")
                or item.get("value")
                or item.get("title")
                or ""
            ).strip()
        else:
            text = str(item).strip()
        if text:
            result.append(text)
    return result


def _extract_version(raw: Any) -> str:
    text = _clean_optional_text(raw)
    if not text:
        return ""
    match = _VERSION_PREFIX_RE.match(text)
    if not match:
        return text
    return match.group(1).strip()


def _version_key(version: str) -> tuple[int, ...]:
    numbers = tuple(int(value) for value in _VERSION_NUMBER_RE.findall(version))
    return numbers or (-1,)


def _note_sort_key(note: PatchNote) -> tuple[tuple[int, ...], int]:
    # Earlier source positions are normally newer, hence the negative index.
    return (_version_key(note.version), -note.source_order)


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
