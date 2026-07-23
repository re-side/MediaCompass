import unittest
from pathlib import Path

from mediacompass.catalog import load_catalog
from mediacompass.models import MediaItem
from mediacompass.recommender import (
    build_tfidf,
    cosine_similarity,
    recommend,
    tokenize,
)


ROOT = Path(__file__).resolve().parents[1]


class RecommenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(ROOT / "data" / "catalog.json")
        cls.by_id = {item.id: item for item in cls.catalog}

    def test_tokenize_removes_common_words(self):
        self.assertEqual(tokenize("Космос и путешествие в мире"), ["космос", "путешествие", "мире"])

    def test_tfidf_creates_vectors(self):
        vectors = build_tfidf(["космос исследование", "магия приключение"])
        self.assertEqual(len(vectors), 2)
        self.assertIn("космос", vectors[0])

    def test_cosine_of_same_vector_is_one(self):
        vector = {"космос": 0.5, "тайна": 0.8}
        self.assertAlmostEqual(cosine_similarity(vector, vector), 1.0)

    def test_recommendations_exclude_liked_item(self):
        liked = [self.by_id["movie_interstellar"]]
        result = recommend(self.catalog, liked, limit=20)
        self.assertNotIn("movie_interstellar", {item["id"] for item in result})

    def test_space_preference_returns_related_item(self):
        liked = [self.by_id["movie_interstellar"]]
        result = recommend(self.catalog, liked, limit=5)
        ids = {item["id"] for item in result}
        self.assertTrue(ids & {"game_outer_wilds", "book_martian", "board_terraforming_mars"})

    def test_type_filter_returns_only_books(self):
        liked = [self.by_id["movie_dune"]]
        result = recommend(self.catalog, liked, media_type="book", limit=8)
        self.assertTrue(result)
        self.assertTrue(all(item["type"] == "book" for item in result))

    def test_minimum_rating_filter(self):
        liked = [self.by_id["movie_lotr"]]
        result = recommend(self.catalog, liked, min_rating=9.0, limit=20)
        self.assertTrue(all(item["rating"] >= 9.0 for item in result))

    def test_score_is_in_percent_range(self):
        liked = [self.by_id["game_cyberpunk"]]
        result = recommend(self.catalog, liked)
        self.assertTrue(all(0 <= item["score"] <= 100 for item in result))

    def test_explanation_is_present(self):
        liked = [self.by_id["book_dune"]]
        result = recommend(self.catalog, liked)
        self.assertTrue(all(item["reasons"] for item in result))

    def test_empty_preferences_return_empty_list(self):
        self.assertEqual(recommend(self.catalog, []), [])

    def test_external_candidate_can_enter_recommendations(self):
        liked = [self.by_id["movie_interstellar"]]
        external = MediaItem(
            id="openlibrary:external-space-book",
            type="book",
            title="Космическая экспедиция",
            description="Исследование космоса и выживание экипажа",
            genres=["научная фантастика"],
            tags=["космос", "исследование", "выживание"],
            rating=9.0,
            source="Open Library",
        )
        result = recommend(self.catalog + [external], liked, limit=3)
        self.assertIn(external.id, {item["id"] for item in result})


if __name__ == "__main__":
    unittest.main()
