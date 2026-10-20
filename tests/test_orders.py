import unittest
from datetime import datetime

from src.queries.orders import get_order, get_order_items, get_order_payments


class TestOrders(unittest.TestCase):
    def test_get_order_existing(self):
        order = get_order("548df2c6e5f089574614894bca78acf5")

        self.assertIsNotNone(order)
        self.assertEqual(order["order_status"], "delivered")

    def test_get_order_not_found(self):
        order = get_order("pedido_inexistente")

        self.assertIsNone(order)

    def test_get_order_items_existing(self):
        items = get_order_items("548df2c6e5f089574614894bca78acf5")

        self.assertEqual(len(items), 2)

    def test_get_order_items_not_found(self):
        items = get_order_items("pedido_inexistente")

        self.assertEqual(items, [])


    def test_get_order_carrier_date(self):
        order = get_order("548df2c6e5f089574614894bca78acf5")

        self.assertIsNotNone(order["carrier_date"])

    def test_get_order_never_shipped_has_no_carrier_date(self):
        # Pedido cancelado que nunca salió del vendedor
        order = get_order("1b9ecfe83cdc259250e1a8aca174f0ad")

        self.assertEqual(order["order_status"], "canceled")
        self.assertIsNone(order["carrier_date"])

    def test_get_order_items_freight_and_category(self):
        items = get_order_items("548df2c6e5f089574614894bca78acf5")

        self.assertEqual(items[0]["freight_value"], 3.94)
        self.assertEqual(items[0]["category"], "eletronicos")

    def test_get_order_items_without_category_keeps_item(self):
        # El producto no tiene categoría: el LEFT JOIN no tiene que perder el ítem
        items = get_order_items("0046e1d57f4c07c8c92ab26be8c3dfc0")

        self.assertGreater(len(items), 0)
        self.assertIsNone(items[0]["category"])

    def test_get_order_payments(self):
        payments = get_order_payments("548df2c6e5f089574614894bca78acf5")

        self.assertEqual(payments["total"], 81.0)
        self.assertEqual(payments["payments"][0]["type"], "credit_card")

    def test_get_order_payments_total_adds_all_payments(self):
        # 1 tarjeta + 6 vouchers
        payments = get_order_payments("00c405bd71187154a7846862f585a9d4")

        self.assertEqual(len(payments["payments"]), 7)
        self.assertEqual(payments["total"], 46.69)

    def test_get_order_payments_not_found(self):
        payments = get_order_payments("pedido_inexistente")

        self.assertEqual(payments, {"total": None, "payments": []})

    def test_get_order_without_payments_has_unknown_total(self):
        # Único pedido del dataset sin pagos: tiene una reseña de 1 estrella.
        # El total tiene que ser None, no 0, para no leerse como "no pagó nada".
        payments = get_order_payments("bfbd0f9bdef84302105ad712db648a6c")

        self.assertIsNone(payments["total"])
        self.assertEqual(payments["payments"], [])

    def test_get_order_as_of_hides_future_delivery(self):
        # Despachado el 02/03, llegó el 02/04: el 21/03 todavía estaba en camino
        order = get_order("543ab3128139efe78bf5e8006ae25087", as_of=datetime(2018, 3, 21))

        self.assertEqual(order["order_status"], "shipped")
        self.assertIsNone(order["delivered_date"])
        self.assertIsNotNone(order["carrier_date"])
        self.assertEqual(order["estimated_delivery_date"], datetime(2018, 3, 19))

    def test_get_order_as_of_before_shipping(self):
        order = get_order("543ab3128139efe78bf5e8006ae25087", as_of=datetime(2018, 3, 1))

        self.assertEqual(order["order_status"], "processing")
        self.assertIsNone(order["carrier_date"])

    def test_get_order_as_of_after_delivery(self):
        order = get_order("543ab3128139efe78bf5e8006ae25087", as_of=datetime(2018, 4, 10))

        self.assertEqual(order["order_status"], "delivered")
        self.assertIsNotNone(order["delivered_date"])

    def test_get_order_as_of_before_purchase_does_not_exist(self):
        order = get_order("543ab3128139efe78bf5e8006ae25087", as_of=datetime(2018, 1, 1))

        self.assertIsNone(order)

    def test_get_order_as_of_keeps_canceled(self):
        # No hay fecha de cancelación: el estado final se mantiene
        order = get_order("808c7c69c2778bdf4689eee0286e2bef", as_of=datetime(2018, 12, 31))

        self.assertEqual(order["order_status"], "canceled")

if __name__ == "__main__":
    unittest.main()
