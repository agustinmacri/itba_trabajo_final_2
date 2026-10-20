import unittest
from datetime import datetime

from src.queries.sellers import get_seller_history

SELLER_ID = "7d13fca15225358621be4086e1eb0964"
# Este vendedor tiene 4 reseñas malas antes de esta fecha y 94 después
AS_OF = datetime(2018, 3, 21)


class TestSellers(unittest.TestCase):
    def test_get_seller_history_only_uses_the_past(self):
        history = get_seller_history(SELLER_ID, as_of=AS_OF)

        bad_reviews = round(history["seller_bad_review_rate"] * history["reviews"])
        self.assertEqual(bad_reviews, 4)

    def test_overdue_undelivered_orders_count_as_late(self):
        # A as_of: 22 entregados (ninguno tarde) y 7 vencidos sin entregar.
        # Antes los 7 no contaban y el vendedor aparecía con 0% de atraso.
        history = get_seller_history(SELLER_ID, as_of=AS_OF)

        self.assertEqual(history["delivered_orders"], 22)
        self.assertEqual(history["overdue_orders"], 7)
        self.assertEqual(history["seller_late_rate"], round(7 / 29, 3))

    def test_recent_bad_reviews_are_before_as_of(self):
        history = get_seller_history(SELLER_ID, as_of=AS_OF)

        self.assertLessEqual(len(history["recent_bad_reviews"]), 5)
        for review in history["recent_bad_reviews"]:
            self.assertLess(review["creation_date"], AS_OF)

    def test_later_as_of_sees_more_reviews(self):
        before = get_seller_history(SELLER_ID, as_of=AS_OF)
        after = get_seller_history(SELLER_ID, as_of=datetime(2018, 9, 1))

        self.assertGreater(after["reviews"], before["reviews"])

    def test_platform_rates_are_rates(self):
        history = get_seller_history(SELLER_ID, as_of=AS_OF)

        self.assertTrue(0 <= history["platform_late_rate"] <= 1)
        self.assertTrue(0 <= history["platform_bad_review_rate"] <= 1)

    def test_seller_without_history_yet(self):
        # Antes de que existiera el dataset: no hay datos, las tasas son None
        history = get_seller_history(SELLER_ID, as_of=datetime(2016, 1, 1))

        self.assertEqual(history["orders"], 0)
        self.assertIsNone(history["seller_late_rate"])
        self.assertIsNone(history["seller_bad_review_rate"])
        self.assertEqual(history["recent_bad_reviews"], [])

    def test_seller_not_found(self):
        history = get_seller_history("vendedor_inexistente", as_of=AS_OF)

        self.assertIsNone(history)


if __name__ == "__main__":
    unittest.main()
