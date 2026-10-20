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

    def test_context_does_not_see_the_future(self):
        # "não recebi o produto", escrita el 21/03: el pedido llegó el 02/04.
        # El agente tiene que verlo como no entregado, no como "el cliente miente".
        context = get_case_context("00397dc753e8c52a2dd4d73a20b88ae7")
        order = context["orders"][0]

        self.assertEqual(context["as_of"], context["review"]["creation_date"])
        self.assertEqual(order["order_status"], "shipped")
        self.assertIsNone(order["delivered_date"])

    def test_no_order_date_after_as_of(self):
        # Pedido despachado después de la reseña: tampoco se ve el despacho
        context = get_case_context("006aeabb2a1ff6d8074ecb4b56afd4d4")

        for order in context["orders"]:
            for key in ("purchase_date", "carrier_date", "delivered_date"):
                if order[key] is not None:
                    self.assertLess(order[key], context["as_of"])
        self.assertEqual(context["orders"][0]["order_status"], "processing")

    def test_order_never_shipped(self):
        # Pedido cancelado sin despacho, con ítems y vendedor
        context = get_case_context("5abeb6e73481b9ace03a85e343f08e47")

        self.assertIsNone(context["orders"][0]["carrier_date"])
        self.assertGreater(len(context["sellers"]), 0)

    def test_order_without_items_has_no_sellers(self):
        # El perfume: pedido unavailable sin ítems, sin vendedores
        context = get_case_context("44c6d194170df31929a4ab4b7ae8512a")

        self.assertEqual(context["orders"][0]["items"], [])
        self.assertTrue(context["orders"][0]["items_missing"])
        self.assertEqual(context["sellers"], [])

    def test_review_linked_only_to_a_later_order(self):
        # "Recebi um produto diferente": el único pedido vinculado se compró después
        # de la reseña. No existía todavía: el caso queda sin pedidos y marcado.
        context = get_case_context("012befdc1333e5840c0c6e34fa6e95ba")

        self.assertEqual(context["orders"], [])
        self.assertTrue(context["orders_missing"])
        self.assertEqual(context["sellers"], [])

    def test_review_with_an_extra_later_order(self):
        # Reseña sobre un pedido de agosto, vinculada también a uno de septiembre
        context = get_case_context("56647f8fbe7430f42719c0510d99e636")

        self.assertEqual(len(context["orders"]), 1)
        self.assertEqual(context["orders"][0]["order_id"], "9e119efc7690fb6c238eca967793fd34")
        self.assertFalse(context["orders_missing"])

    def test_unavailable_order_without_items_still_has_payment(self):
        # "Comprei um perfume Bleu de Chanel, paguei e não recebi": no hay ítems,
        # pero el pago es el monto que el agente puede usar
        context = get_case_context("44c6d194170df31929a4ab4b7ae8512a")
        order = context["orders"][0]

        self.assertEqual(order["order_status"], "unavailable")
        self.assertTrue(order["items_missing"])
        self.assertEqual(order["payments"]["total"], 615.53)

    def test_order_with_items_is_not_flagged(self):
        context = get_case_context("00397dc753e8c52a2dd4d73a20b88ae7")

        self.assertFalse(context["orders"][0]["items_missing"])
        self.assertGreater(context["orders"][0]["payments"]["total"], 0)

    def test_review_not_found(self):
        context = get_case_context("resena_inexistente")

        self.assertIsNone(context)

    def test_context_can_be_converted_to_json(self):
        context = get_case_context("00130cbe1f9d422698c812ed8ded1919")

        data = json.loads(to_json(context))
        self.assertEqual(len(data["orders"]), 2)
