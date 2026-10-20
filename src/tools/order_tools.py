from datetime import datetime

from src.database.connection import get_connection


def _known_at(value: datetime | None, as_of: datetime | None) -> datetime | None:
    # Una fecha posterior a as_of todavía no había pasado: no se muestra.
    if as_of is None or value is None or value < as_of:
        return value
    return None


def get_order(order_id: str, as_of: datetime | None = None) -> dict | None:
    # Con as_of, el pedido se devuelve como estaba en ese momento, no en su estado final.
    # Si no, el agente vería que llegó días después de que el cliente escribió "não recebi".
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

    status = row[1]
    carrier_date = _known_at(row[3], as_of)
    delivered_date = _known_at(row[5], as_of)

    # El estado se reconstruye con las fechas conocidas a as_of.
    # canceled / unavailable no tienen fecha de cancelación: quedan con su estado final.
    if as_of is not None and status not in ("canceled", "unavailable"):
        if delivered_date is not None:
            status = "delivered"
        elif carrier_date is not None:
            status = "shipped"
        else:
            status = "processing"

    return {
        "order_id": row[0],
        "order_status": status,
        "purchase_date": row[2],
        # Cuándo el vendedor se lo entregó al transportista. None si nunca se despachó.
        "carrier_date": carrier_date,
        # La fecha estimada se conoce desde la compra: no se oculta.
        "estimated_delivery_date": row[4],
        "delivered_date": delivered_date,
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


def get_order_payments(order_id: str) -> dict:
    # Lo que pagó el cliente. Es el único monto confiable cuando el pedido no tiene ítems.
    query = """
        SELECT
            payment_type,
            payment_installments,
            payment_value
        FROM olist.order_payments
        WHERE order_id = %s
        ORDER BY payment_sequential
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (order_id,))
            rows = cursor.fetchall()

    payments = []

    for row in rows:
        payment = {
            "type": row[0],
            "installments": row[1],
            "value": float(row[2]),
        }
        payments.append(payment)

    return {
        "total": round(sum(p["value"] for p in payments), 2),
        "payments": payments,
    }
