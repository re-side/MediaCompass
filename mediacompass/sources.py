from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

from .models import MediaItem

USER_AGENT = "MediaCompass/1.0 (educational practice project)"

# Внешние каталоги часто возвращают английские темы. Небольшой словарь помогает
# сопоставлять их с русскими тегами локального учебного каталога.
TERM_TRANSLATIONS = {
    "science fiction": "научная фантастика",
    "fantasy": "фэнтези",
    "adventure": "приключения",
    "action": "боевик",
    "role-playing": "ролевая игра",
    "role playing": "ролевая игра",
    "strategy": "стратегия",
    "simulation": "симулятор",
    "space": "космос",
    "dystopia": "антиутопия",
    "mystery": "тайна",
    "detective": "детектив",
    "horror": "ужасы",
    "history": "история",
    "magic": "магия",
    "survival": "выживание",
}


def normalize_terms(values: list[str], limit: int = 12) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        normalized = TERM_TRANSLATIONS.get(cleaned.lower(), cleaned.lower())
        if normalized not in result:
            result.append(normalized)
    return result[:limit]


def _request(url: str, timeout: int = 8) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def search_open_library(query: str, limit: int = 8) -> list[MediaItem]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "fields": "key,title,author_name,first_publish_year,subject,cover_i,ratings_average,ratings_count",
            "limit": min(max(limit, 1), 12),
        }
    )
    payload = json.loads(_request(f"https://openlibrary.org/search.json?{params}"))
    result = []
    for doc in payload.get("docs", []):
        key = doc.get("key", "")
        cover_id = doc.get("cover_i")
        authors = doc.get("author_name") or []
        subjects = normalize_terms(doc.get("subject") or [], 12)
        count = doc.get("ratings_count") or 0
        popularity = min(math.log10(count + 1) / 5, 1.0)
        result.append(
            MediaItem(
                id=f"openlibrary:{key}",
                type="book",
                title=doc.get("title", "Без названия"),
                year=doc.get("first_publish_year"),
                description="Книга " + ("автора " + ", ".join(authors[:2]) if authors else ""),
                genres=subjects[:4],
                tags=subjects[4:10],
                rating=float(doc.get("ratings_average") or 0) * 2,
                popularity=popularity,
                source="Open Library",
                source_url=f"https://openlibrary.org{key}",
                image_url=(
                    f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                    if cover_id
                    else ""
                ),
            )
        )
    return result


def _steam_details(app_id: int) -> dict:
    params = urllib.parse.urlencode({"appids": app_id, "l": "russian", "cc": "ru"})
    payload = json.loads(_request(f"https://store.steampowered.com/api/appdetails?{params}"))
    entry = payload.get(str(app_id), {})
    return entry.get("data", {}) if entry.get("success") else {}


def _release_year(details: dict) -> int | None:
    date_text = (details.get("release_date") or {}).get("date", "")
    for token in date_text.replace(",", " ").split():
        if token.isdigit() and len(token) == 4:
            year = int(token)
            if 1950 <= year <= datetime.now().year + 2:
                return year
    return None


def search_steam(query: str, limit: int = 8) -> list[MediaItem]:
    params = urllib.parse.urlencode({"term": query, "l": "russian", "cc": "ru"})
    payload = json.loads(
        _request(f"https://store.steampowered.com/api/storesearch/?{params}")
    )
    result = []
    for item in payload.get("items", [])[:limit]:
        price_data = item.get("price") or {}
        app_id = item.get("id")
        try:
            details = _steam_details(app_id)
        except Exception:
            # Поиск остаётся полезным, даже если дополнительный запрос временно не удался.
            details = {}
        genres = normalize_terms([value.get("description", "") for value in details.get("genres", [])], 6)
        categories = normalize_terms([value.get("description", "") for value in details.get("categories", [])], 8)
        recommendations = (details.get("recommendations") or {}).get("total", 0)
        metacritic = (details.get("metacritic") or {}).get("score", 0)
        detailed_price = details.get("price_overview") or {}
        result.append(
            MediaItem(
                id=f"steam:{app_id}",
                type="game",
                title=item.get("name", "Без названия"),
                year=_release_year(details),
                description=(details.get("short_description") or "Компьютерная игра из магазина Steam")[:600],
                genres=genres or ["компьютерная игра"],
                tags=categories or ["steam"],
                rating=round(metacritic / 10, 1) if metacritic else 0.0,
                popularity=min(math.log10(recommendations + 1) / 6, 1.0),
                source="Steam Store",
                source_url=f"https://store.steampowered.com/app/{app_id}/",
                image_url=item.get("tiny_image", ""),
                price=(
                    detailed_price.get("final", price_data.get("final")) / 100
                    if detailed_price.get("final", price_data.get("final")) is not None
                    else None
                ),
                discount=detailed_price.get("discount_percent", price_data.get("discount_percent")),
                currency=detailed_price.get("currency", price_data.get("currency", "RUB")),
            )
        )
    return result


def search_wikipedia_movies(query: str, limit: int = 8) -> list[MediaItem]:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": f'intitle:"{query}" фильм',
            "gsrnamespace": 0,
            "gsrlimit": min(max(limit, 1), 12),
            "prop": "extracts|pageimages|info",
            "exintro": 1,
            "explaintext": 1,
            "piprop": "thumbnail",
            "pithumbsize": 600,
            "inprop": "url",
            "format": "json",
            "formatversion": 2,
        }
    )
    payload = json.loads(_request(f"https://ru.wikipedia.org/w/api.php?{params}"))
    result = []
    pages = payload.get("query", {}).get("pages", [])
    normalized_query = query.strip().lower()
    pages.sort(key=lambda page: (normalized_query not in page.get("title", "").lower(), page.get("index", 999)))
    for item in pages:
        thumbnail = item.get("thumbnail") or {}
        description = (item.get("extract") or "Статья о фильме")[:600]
        lowered = description.lower()
        keyword_map = {
            "косм": "космос", "фантаст": "научная фантастика",
            "детектив": "детектив", "триллер": "триллер", "драм": "драма",
            "приключ": "приключения", "комеди": "комедия", "ужас": "ужасы",
            "антиутоп": "антиутопия", "маг": "магия", "войн": "война",
        }
        tags = [tag for keyword, tag in keyword_map.items() if keyword in lowered]
        result.append(
            MediaItem(
                id=f"wikipedia:{item.get('pageid', '')}",
                type="movie",
                title=item.get("title", "Без названия"),
                description=description,
                genres=tags[:3] or ["фильм"],
                tags=tags[3:] + ["кино"],
                source="Wikipedia API",
                source_url=item.get("fullurl", ""),
                image_url=thumbnail.get("source", ""),
            )
        )
    return result


def search_boardgamegeek(query: str, limit: int = 8) -> list[MediaItem]:
    params = urllib.parse.urlencode({"query": query, "type": "boardgame"})
    root = ET.fromstring(
        _request(f"https://boardgamegeek.com/xmlapi2/search?{params}")
    )
    result = []
    for node in root.findall("item")[:limit]:
        name = node.find("name")
        year = node.find("yearpublished")
        item_id = node.attrib.get("id", "")
        result.append(
            MediaItem(
                id=f"bgg:{item_id}",
                type="board_game",
                title=name.attrib.get("value", "Без названия") if name is not None else "Без названия",
                year=int(year.attrib["value"]) if year is not None and year.attrib.get("value", "").isdigit() else None,
                description="Настольная игра из базы BoardGameGeek",
                genres=["board game"],
                tags=["tabletop"],
                source="BoardGameGeek",
                source_url=f"https://boardgamegeek.com/boardgame/{item_id}",
            )
        )
    return result
