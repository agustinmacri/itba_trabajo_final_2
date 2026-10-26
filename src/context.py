from src.queries.orders import get_order, get_order_items, get_order_payments
from src.queries.reviews import get_review
from src.queries.sellers import get_seller_history


def get_case_context(review_id: str) -> dict | None:
    # El paquete de contexto que recibe el LLM: lo junta el código antes de llamarlo.
    review = get_review(review_id)

    if review is None:
        return None

    # Todo el paquete se arma como estaba el día de la reseña: pedidos y vendedores.
    as_of = review["creation_date"]
    orders = []
    seller_ids = set()

    for order_id in review["order_ids"]:
        order = get_order(order_id, as_of=as_of)
        if order is None:
            continue

        order["items"] = get_order_items(order_id)
        order["payments"] = get_order_payments(order_id)
        # 775 pedidos (casi todos "unavailable") no tienen ítems pero sí pago.
        # Sin este flag, una lista vacía se lee como "no compró nada"; en realidad no sabemos qué compró.
        order["items_missing"] = len(order["items"]) == 0
        seller_ids.update(item["seller_id"] for item in order["items"])
        orders.append(order)

    # Pedidos sin ítems no tienen vendedor: la lista queda vacía.
    sellers = [
        get_seller_history(seller_id, as_of=as_of)
        for seller_id in sorted(seller_ids)
    ]

    return {
        # True si la reseña no tiene ningún pedido anterior a su fecha: el dataset la vinculó
        # a una compra posterior y no sabemos de qué pedido habla.
        "orders_missing": len(orders) == 0,
        # El "hoy" del caso: el LLM lo necesita para saber, por ejemplo, si un pedido está vencido.
        "as_of": as_of,
        "review": review,
        "orders": orders,
        "sellers": sellers,
    }
