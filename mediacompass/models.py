from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MediaItem:
    id: str
    type: str
    title: str
    year: int | None = None
    description: str = ""
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    rating: float = 0.0
    popularity: float = 0.0
    source: str = "local"
    source_url: str = ""
    image_url: str = ""
    price: float | None = None
    discount: int | None = None
    currency: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaItem":
        allowed = cls.__dataclass_fields__.keys()
        prepared = {key: data.get(key) for key in allowed if key in data}
        prepared.setdefault("genres", [])
        prepared.setdefault("tags", [])
        return cls(**prepared)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def feature_text(self) -> str:
        # Жанры и теги повторяются, чтобы важные короткие признаки не потерялись
        # на фоне длинного описания при расчёте TF-IDF.
        parts = [self.title] + self.genres * 3 + self.tags * 2 + [self.description]
        return " ".join(str(part) for part in parts if part)
