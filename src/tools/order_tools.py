from src.database.connection import get_connection


def get_order(order_id: str) -> dict | None:
    query = """
        SELECT
            order_id,
            order_status,
            order_purchase_timestamp,
            order_delivered_carrier_date,
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
        # Cuándo el vendedor se lo entregó al transportista. None si nunca se despachó.
        "carrier_date": row[3],
        "estimated_delivery_date": row[4],
        "delivered_date": row[5],
    }


def get_order_items(order_id: str) -> list[dict]:
    query = """
        SELECT
            i.order_item_id,
            i.product_id,
            i.seller_id,
            i.price,
            i.freight_value,
            p.product_category_name
        FROM olist.order_items i
        LEFT JOIN olist.products p ON p.product_id = i.product_id
        WHERE i.order_id = %s
        ORDER BY i.order_item_id
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
            # Envío que pagó el cliente por este ítem.
            "freight_value": float(row[4]),
            # LEFT JOIN: hay productos sin categoría, y así no se pierde el ítem.
            "category": row[5],
        }
        items.append(item)

    return items
