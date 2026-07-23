from __future__ import annotations

import math
import re
from collections import Counter

from .models import MediaItem

TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
EXTERNAL_ID_PREFIXES = ("openlibrary:", "steam:", "wikipedia:", "bgg:")
STOP_WORDS = {
    "и", "в", "во", "на", "с", "со", "к", "по", "о", "об", "для",
    "из", "это", "как", "а", "но", "или", "the", "and", "of", "to",
    "in", "a", "an", "with", "for", "on",
}


def tokenize(text: str) -> list[str]:
    tokens = [token.lower().replace("ё", "е") for token in TOKEN_RE.findall(text)]
    return [token for token in tokens if token not in STOP_WORDS and len(token) > 1]


def build_tfidf(documents: list[str]) -> list[dict[str, float]]:
    # Сначала считаем, в скольких документах встречается каждое слово.
    tokenized = [tokenize(document) for document in documents]
    document_count = len(tokenized)
    document_frequency: Counter[str] = Counter()

    for tokens in tokenized:
        document_frequency.update(set(tokens))

    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        counts = Counter(tokens)
        total = max(len(tokens), 1)
        vector: dict[str, float] = {}
        for token, count in counts.items():
            term_frequency = count / total
            inverse_frequency = math.log(
                (1 + document_count) / (1 + document_frequency[token])
            ) + 1
            vector[token] = term_frequency * inverse_frequency
        vectors.append(vector)
    return vectors


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot_product = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def average_vectors(vectors: list[dict[str, float]]) -> dict[str, float]:
    if not vectors:
        return {}
    result: dict[str, float] = {}
    for vector in vectors:
        for token, value in vector.items():
            result[token] = result.get(token, 0.0) + value
    count = len(vectors)
    return {token: value / count for token, value in result.items()}


def _normalize_rating(value: float) -> float:
    if value <= 1:
        return max(0.0, value)
    return min(max(value / 10, 0.0), 1.0)


def _explanation(candidate: MediaItem, liked: list[MediaItem]) -> list[str]:
    liked_genres = {value.lower() for item in liked for value in item.genres}
    liked_tags = {value.lower() for item in liked for value in item.tags}
    genres = [value for value in candidate.genres if value.lower() in liked_genres]
    tags = [value for value in candidate.tags if value.lower() in liked_tags]

    reasons: list[str] = []
    if genres:
        reasons.append("Совпавшие жанры: " + ", ".join(genres[:3]))
    if tags:
        reasons.append("Общие темы: " + ", ".join(tags[:4]))
    if candidate.rating >= 8:
        reasons.append(f"Высокий рейтинг: {candidate.rating:.1f}/10")
    if candidate.discount:
        reasons.append(f"Скидка: {candidate.discount}%")
    if not reasons:
        reasons.append("Похожее текстовое описание и общий профиль признаков")
    return reasons[:3]


def recommend(
    catalog: list[MediaItem],
    liked: list[MediaItem],
    media_type: str = "all",
    min_rating: float = 0.0,
    limit: int = 8,
) -> list[dict]:
    if not liked:
        return []

    candidates = [
        item
        for item in catalog
        if item.id not in {liked_item.id for liked_item in liked}
        and (media_type == "all" or item.type == media_type)
        and item.rating >= min_rating
    ]
    if not candidates:
        return []

    # Понравившиеся объекты и кандидаты векторизуются вместе, чтобы веса слов
    # рассчитывались в одном пространстве признаков.
    all_items = liked + candidates
    vectors = build_tfidf([item.feature_text() for item in all_items])
    profile = average_vectors(vectors[: len(liked)])

    ranked = []
    for item, vector in zip(candidates, vectors[len(liked) :]):
        similarity = cosine_similarity(profile, vector)
        rating_score = _normalize_rating(item.rating)
        popularity_score = min(max(item.popularity, 0.0), 1.0)
        score = 0.72 * similarity + 0.18 * rating_score + 0.10 * popularity_score
        ranked.append(
            {
                **item.to_dict(),
                "similarity": round(similarity, 4),
                "score": round(score * 100, 1),
                "reasons": _explanation(item, liked),
            }
        )

    ranked.sort(key=lambda item: (item["score"], item["rating"]), reverse=True)
    result_limit = max(1, min(limit, 20))
    selected = ranked[:result_limit]

    # Если пользователь добавил данные из внешнего источника, показываем лучшего
    # такого кандидата в короткой выдаче. Его рассчитанный балл не изменяется.
    external = [
        item for item in ranked
        if item["id"].startswith(EXTERNAL_ID_PREFIXES)
    ]
    external_is_visible = any(
        item["id"].startswith(EXTERNAL_ID_PREFIXES) for item in selected
    )
    if external and selected and not external_is_visible:
        selected[-1] = external[0]

    return selected
