import unittest

from src.queries.reviews import get_review


class TestReviews(unittest.TestCase):
    def test_get_review_existing(self):
        review = get_review("00397dc753e8c52a2dd4d73a20b88ae7")

        self.assertEqual(review["score"], 1)
        self.assertEqual(review["order_ids"], ["543ab3128139efe78bf5e8006ae25087"])

    def test_get_review_with_two_orders(self):
        # Una reseña que cubre dos pedidos del mismo cliente
        review = get_review("00130cbe1f9d422698c812ed8ded1919")

        self.assertEqual(len(review["order_ids"]), 2)

    def test_get_review_not_found(self):
        review = get_review("resena_inexistente")

        self.assertIsNone(review)


if __name__ == "__main__":
    unittest.main()
