import json
import unittest

from src.context import get_case_context
from src.serialization import to_json


class TestCaseContext(unittest.TestCase):
    def test_simple_review(self):
        # 1 pedido, 1 vendedor
        context = get_case_context("00397dc753e8c52a2dd4d73a20b88ae7")

        self.assertEqual(len(context["orders"]), 1)
        self.assertEqual(len(context["orders"][0]["items"]), 1)
        self.assertEqual(len(context["sellers"]), 1)

    def test_review_with_two_orders_and_two_sellers(self):
        context = get_case_context("00130cbe1f9d422698c812ed8ded1919")

        self.assertEqual(len(context["orders"]), 2)
        self.assertEqual(len(context["sellers"]), 2)

    def test_sellers_history_uses_review_date(self):
        context = get_case_context("00397dc753e8c52a2dd4d73a20b88ae7")

        self.assertEqual(context["sellers"][0]["as_of"], context["review"]["creation_date"])

    def test_order_never_shipped(self):
        # Pedido cancelado sin despacho, con ítems y vendedor
        context = get_case_context("5abeb6e73481b9ace03a85e343f08e47")

        self.assertIsNone(context["orders"][0]["carrier_date"])
        self.assertGreater(len(context["sellers"]), 0)

    def test_order_without_items_has_no_sellers(self):
        # Pedido cancelado antes de tener ítems: el caso existe pero sin vendedores
        context = get_case_context("012befdc1333e5840c0c6e34fa6e95ba")

        self.assertEqual(context["orders"][0]["items"], [])
        self.assertEqual(context["sellers"], [])

    def test_review_not_found(self):
        context = get_case_context("resena_inexistente")

        self.assertIsNone(context)

    def test_context_can_be_converted_to_json(self):
        context = get_case_context("00130cbe1f9d422698c812ed8ded1919")

        data = json.loads(to_json(context))
        self.assertEqual(len(data["orders"]), 2)
