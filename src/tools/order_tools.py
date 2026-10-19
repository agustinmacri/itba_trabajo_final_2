from src.database.connection import get_connection


def get_order(order_id: str) -> dict | None:
    query = """
        SELECT
            order_id,
            order_status,
            order_purchase_timestamp,
            order_estimated_delivery_date,
            order_delivered_customer_date
        FROM olist.orders
        WHERE order_id = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (order_id,))
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "order_id": row[0],
        "order_status": row[1],
        "purchase_date": row[2],
        "estimated_delivery_date": row[3],
        "delivered_date": row[4],
    }


def get_order_items(order_id: str) -> list[dict]:
    query = """
        SELECT
            order_item_id,
            product_id,
            seller_id,
            price
        FROM olist.order_items
        WHERE order_id = %s
        ORDER BY order_item_id
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (order_id,))
            rows = cursor.fetchall()

    items = []

    for row in rows:
        item = {
            "order_item_id": row[0],
            "product_id": row[1],
            "seller_id": row[2],
            "price": float(row[3]),
        }
        items.append(item)

    return items
