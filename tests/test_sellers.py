import unittest
from datetime import datetime

from src.queries.sellers import get_seller_history

SELLER_ID = "7d13fca15225358621be4086e1eb0964"
# Este vendedor tiene 23 reseñas (4 malas) antes de esta fecha y muchas más después
AS_OF = datetime(2018, 3, 21)


class TestSellers(unittest.TestCase):
    def test_get_seller_history_only_uses_the_past(self):
        # 23 reseñas antes de AS_OF (contadas aparte en SQL); con una fecha posterior hay más
        history = get_seller_history(SELLER_ID, as_of=AS_OF)
        later = get_seller_history(SELLER_ID, as_of=datetime(2018, 9, 1))

        self.assertEqual(history["reviews"], 23)
        self.assertGreater(later["reviews"], history["reviews"])

    def test_review_linked_to_a_later_order_does_not_count_for_its_seller(self):
        # La reseña 0857872f (1 estrella, del 18/05) está vinculada solo a un pedido de este
        # vendedor del 23/06: no puede contar en su contra. Contando aparte en SQL, al 01/06
        # el vendedor tiene 155 reseñas; con esa reseña mal atribuida serían 156.
        history = get_seller_history("7040e82f899a04d1b434b795a43b4617", as_of=datetime(2018, 6, 1))

        self.assertEqual(history["reviews"], 155)

    def test_overdue_undelivered_orders_count_as_late(self):
        # A as_of: 22 entregados (ninguno tarde) y 7 vencidos sin entregar.
        # Antes los 7 no contaban y el vendedor aparecía con 0% de atraso.
        history = get_seller_history(SELLER_ID, as_of=AS_OF)

        self.assertEqual(history["delivered_orders"], 22)
        self.assertEqual(history["overdue_orders"], 7)
        self.assertEqual(history["seller_late_rate"], round(7 / 29, 3))

    def test_never_delivered_orders_count_as_overdue(self):
        # Este vendedor tiene 46 pedidos vencidos que nunca llegaron (fecha de entrega NULL).
        # El vendedor de arriba no sirve para esto: sus vencidos llegaron todos después.
        history = get_seller_history("cc419e0650a3c5ba77189a1882b7556a", as_of=datetime(2018, 9, 1))

        self.assertEqual(history["delivered_orders"], 1651)
        self.assertEqual(history["overdue_orders"], 46)

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

    def test_few_data_hides_seller_rates(self):
        # 3 reseñas y 3 entregas a esta fecha: menos que MIN_SAMPLE_FOR_RATE.
        # Las tasas vuelven None, pero los conteos y la plataforma siguen.
        history = get_seller_history("0015a82c2db000af6aaaf3ae2ecb0532", as_of=AS_OF)

        self.assertEqual(history["reviews"], 3)
        self.assertIsNone(history["seller_bad_review_rate"])
        self.assertIsNone(history["seller_late_rate"])
        self.assertIsNotNone(history["platform_bad_review_rate"])

    def test_seller_not_found(self):
        history = get_seller_history("vendedor_inexistente", as_of=AS_OF)

        self.assertIsNone(history)


if __name__ == "__main__":
    unittest.main()
