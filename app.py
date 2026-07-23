from __future__ import annotations

import argparse
import csv
import io
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mediacompass.catalog import load_catalog, search_catalog
from mediacompass.models import MediaItem
from mediacompass.recommender import recommend
from mediacompass.sources import (
    search_boardgamegeek,
    search_open_library,
    search_steam,
    search_wikipedia_movies,
)

PROJECT_DIR = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_DIR / "static"
CATALOG = load_catalog(PROJECT_DIR / "data" / "catalog.json")


class MediaCompassHandler(BaseHTTPRequestHandler):
    server_version = "MediaCompass/1.0"

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_static(self, request_path: str):
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        content_type, _ = mimetypes.guess_type(target.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/health":
            self._send_json({"status": "ok", "items": len(CATALOG)})
            return

        if parsed.path == "/api/catalog":
            items = search_catalog(
                CATALOG,
                query.get("q", [""])[0],
                query.get("type", ["all"])[0],
            )
            self._send_json([item.to_dict() for item in items])
            return

        if parsed.path == "/api/source":
            source = query.get("source", [""])[0]
            search_query = query.get("q", [""])[0].strip()
            if not search_query:
                self._send_json({"error": "Введите поисковый запрос"}, HTTPStatus.BAD_REQUEST)
                return
            try:
                if source == "openlibrary":
                    items = search_open_library(search_query)
                elif source == "steam":
                    items = search_steam(search_query)
                elif source == "wikipedia":
                    items = search_wikipedia_movies(search_query)
                elif source == "bgg":
                    items = search_boardgamegeek(search_query)
                else:
                    self._send_json({"error": "Неизвестный источник"}, HTTPStatus.BAD_REQUEST)
                    return
                self._send_json([item.to_dict() for item in items])
            except Exception as error:
                self._send_json(
                    {"error": "Внешний источник временно недоступен", "details": str(error)},
                    HTTPStatus.BAD_GATEWAY,
                )
            return

        self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({"error": "Некорректный JSON"}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/recommend":
            liked = [MediaItem.from_dict(item) for item in payload.get("liked_items", [])]
            external_candidates = [
                MediaItem.from_dict(item) for item in payload.get("candidate_items", [])[:100]
            ]
            # Внешние результаты дополняют локальный каталог. Объекты с одинаковым
            # идентификатором не дублируются.
            candidates_by_id = {item.id: item for item in CATALOG}
            candidates_by_id.update({item.id: item for item in external_candidates})
            result = recommend(
                list(candidates_by_id.values()),
                liked,
                media_type=payload.get("type", "all"),
                min_rating=float(payload.get("min_rating", 0)),
                limit=int(payload.get("limit", 8)),
            )
            self._send_json(result)
            return

        if parsed.path == "/api/export":
            rows = payload.get("items", [])
            stream = io.StringIO()
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["Название", "Тип", "Рейтинг", "Итоговый балл", "Причины"])
            for item in rows:
                writer.writerow(
                    [
                        item.get("title"),
                        item.get("type"),
                        item.get("rating"),
                        item.get("score"),
                        " | ".join(item.get("reasons", [])),
                    ]
                )
            body = ("\ufeff" + stream.getvalue()).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="recommendations.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self._send_json({"error": "Маршрут не найден"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format_string, *args):
        print(f"[{self.log_date_time_string()}] {format_string % args}")


def run(host: str = "127.0.0.1", port: int = 8000):
    server = ThreadingHTTPServer((host, port), MediaCompassHandler)
    print(f"Media Compass запущен: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Остановка сервера")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Медиа-компас")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    run(arguments.host, arguments.port)
