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


if __name__ == "__main__":
    unittest.main()
