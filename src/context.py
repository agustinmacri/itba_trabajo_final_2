from src.tools.order_tools import get_order, get_order_items
from src.tools.review_tools import get_review
from src.tools.seller_tools import get_seller_history


def get_case_context(review_id: str) -> dict | None:
    # El paquete de contexto que recibe el LLM: lo junta el código antes de llamarlo.
    review = get_review(review_id)

    if review is None:
        return None

    orders = []
    seller_ids = set()

    for order_id in review["order_ids"]:
        order = get_order(order_id)
        if order is None:
            continue

        order["items"] = get_order_items(order_id)
        seller_ids.update(item["seller_id"] for item in order["items"])
        orders.append(order)

    # Pedidos cancelados antes de tener ítems no tienen vendedor: la lista queda vacía.
    sellers = [
        get_seller_history(seller_id, as_of=review["creation_date"])
        for seller_id in sorted(seller_ids)
    ]

    return {
        "review": review,
        "orders": orders,
        "sellers": sellers,
    }
