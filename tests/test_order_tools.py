import unittest

from src.tools.order_tools import get_order, get_order_items


class TestOrderTools(unittest.TestCase):
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

if __name__ == "__main__":
    unittest.main()
