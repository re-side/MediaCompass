from __future__ import annotations

import json
from pathlib import Path

from .models import MediaItem


def load_catalog(path: str | Path) -> list[MediaItem]:
    with Path(path).open("r", encoding="utf-8") as source:
        payload = json.load(source)
    return [MediaItem.from_dict(item) for item in payload]


def search_catalog(
    items: list[MediaItem], query: str = "", media_type: str = "all"
) -> list[MediaItem]:
    query = query.strip().lower()
    result = []
    for item in items:
        if media_type != "all" and item.type != media_type:
            continue
        haystack = " ".join([item.title, *item.genres, *item.tags]).lower()
        if query and query not in haystack:
            continue
        result.append(item)
    return result
