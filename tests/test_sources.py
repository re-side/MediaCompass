import io
import json
import unittest
from unittest.mock import patch

from mediacompass.sources import (
    normalize_terms,
    search_boardgamegeek,
    search_open_library,
    search_steam,
    search_wikipedia_movies,
)


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class SourceTests(unittest.TestCase):
    def test_english_subjects_are_translated(self):
        self.assertEqual(
            normalize_terms(["Science Fiction", "Space", "Science Fiction"]),
            ["научная фантастика", "космос"],
        )

    @patch("urllib.request.urlopen")
    def test_open_library_response_is_normalized(self, urlopen):
        payload = {
            "docs": [
                {
                    "key": "/works/OL1W",
                    "title": "Test Book",
                    "author_name": ["Test Author"],
                    "first_publish_year": 2020,
                    "subject": ["Science fiction", "Space"],
                    "cover_i": 123,
                    "ratings_average": 4.5,
                    "ratings_count": 100,
                }
            ]
        }
        urlopen.return_value = FakeResponse(json.dumps(payload).encode("utf-8"))
        result = search_open_library("test")
        self.assertEqual(result[0].type, "book")
        self.assertEqual(result[0].rating, 9.0)
        self.assertEqual(result[0].source, "Open Library")

    @patch("urllib.request.urlopen")
    def test_steam_price_is_converted_from_kopecks(self, urlopen):
        search_payload = {
            "items": [
                {
                    "id": 10,
                    "name": "Test Game",
                    "tiny_image": "image.jpg",
                    "price": {"final": 49900, "discount_percent": 20},
                }
            ]
        }
        details_payload = {
            "10": {
                "success": True,
                "data": {
                    "short_description": "Игра о космическом исследовании",
                    "genres": [{"description": "Adventure"}],
                    "categories": [{"description": "Co-op"}],
                    "metacritic": {"score": 80},
                },
            }
        }
        urlopen.side_effect = [
            FakeResponse(json.dumps(search_payload).encode("utf-8")),
            FakeResponse(json.dumps(details_payload).encode("utf-8")),
        ]
        result = search_steam("test")
        self.assertEqual(result[0].price, 499.0)
        self.assertEqual(result[0].discount, 20)
        self.assertEqual(result[0].genres, ["приключения"])
        self.assertEqual(result[0].rating, 8.0)

    @patch("urllib.request.urlopen")
    def test_bgg_xml_is_normalized(self, urlopen):
        xml = b'<items><item type="boardgame" id="42"><name type="primary" value="Test Board Game"/><yearpublished value="2022"/></item></items>'
        urlopen.return_value = FakeResponse(xml)
        result = search_boardgamegeek("test")
        self.assertEqual(result[0].type, "board_game")
        self.assertEqual(result[0].year, 2022)
        self.assertEqual(result[0].source, "BoardGameGeek")

    @patch("urllib.request.urlopen")
    def test_wikipedia_movie_is_normalized(self, urlopen):
        payload = {
            "query": {
                "pages": [
                    {
                        "pageid": 7,
                        "title": "Test Movie",
                        "extract": "Space story",
                        "fullurl": "https://example.org/movie",
                        "thumbnail": {"source": "https://example.org/image.jpg"},
                    }
                ]
            }
        }
        urlopen.return_value = FakeResponse(json.dumps(payload).encode("utf-8"))
        result = search_wikipedia_movies("test")
        self.assertEqual(result[0].type, "movie")
        self.assertEqual(result[0].source, "Wikipedia API")
        self.assertEqual(result[0].title, "Test Movie")


if __name__ == "__main__":
    unittest.main()
