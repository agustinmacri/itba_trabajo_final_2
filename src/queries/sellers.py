from datetime import datetime

from src.database.connection import get_connection


def get_seller_history(seller_id: str, as_of: datetime) -> dict | None:
    # Todo se calcula solo con datos anteriores a as_of (el "hoy" del caso).
    # Si no, el agente vería reseñas escritas después del caso que está resolviendo.
    stats_query = """
        WITH seller_orders AS (
            SELECT DISTINCT order_id
            FROM olist.order_items
            WHERE seller_id = %(seller_id)s
        ),
        deliveries AS (
            -- Se compara por día: la fecha estimada viene a las 00:00, así que
            -- llegar ese mismo día a la tarde cuenta como a tiempo.
            SELECT
                o.order_id IN (SELECT order_id FROM seller_orders) AS is_seller,
                CAST(o.order_delivered_customer_date AS DATE) > CAST(o.order_estimated_delivery_date AS DATE) AS is_late
            FROM olist.orders o
            WHERE o.order_delivered_customer_date < %(as_of)s
        ),
        reviews AS (
            SELECT
                BOOL_OR(r.order_id IN (SELECT order_id FROM seller_orders)) AS is_seller,
                MIN(r.review_score) <= 2 AS is_bad
            FROM olist.order_reviews r
            WHERE r.review_creation_date < %(as_of)s
            GROUP BY r.review_id
        ),
        -- Cada *_stats es una agregación sin GROUP BY: siempre devuelve exactamente una fila,
        -- aunque no haya datos. Por eso el CROSS JOIN de abajo no multiplica filas.
        -- CAST(... AS INT) convierte true/false en 1/0: el promedio es la proporción.
        order_stats AS (
            SELECT COUNT(*) AS orders
            FROM olist.orders o
            JOIN seller_orders so ON so.order_id = o.order_id
            WHERE o.order_purchase_timestamp < %(as_of)s
        ),
        delivery_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE is_seller) AS delivered_orders,
                CAST(ROUND(AVG(CAST(is_late AS INT)) FILTER (WHERE is_seller), 3) AS FLOAT) AS late_rate,
                CAST(ROUND(AVG(CAST(is_late AS INT)), 3) AS FLOAT) AS platform_late_rate
            FROM deliveries
        ),
        review_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE is_seller) AS reviews,
                CAST(ROUND(AVG(CAST(is_bad AS INT)) FILTER (WHERE is_seller), 3) AS FLOAT) AS bad_review_rate,
                CAST(ROUND(AVG(CAST(is_bad AS INT)), 3) AS FLOAT) AS platform_bad_review_rate
            FROM reviews
        )
        SELECT
            os.orders,
            ds.delivered_orders,
            ds.late_rate,
            ds.platform_late_rate,
            rs.reviews,
            rs.bad_review_rate,
            rs.platform_bad_review_rate
        FROM order_stats os
        CROSS JOIN delivery_stats ds
        CROSS JOIN review_stats rs
    """

    # Las 5 reseñas malas con texto más recientes, para que el LLM lea si hay un patrón.
    recent_query = """
        SELECT DISTINCT
            r.review_id,
            r.review_score,
            r.review_comment_title,
            r.review_comment_message,
            r.review_creation_date
        FROM olist.order_reviews r
        JOIN olist.order_items i ON i.order_id = r.order_id
        WHERE i.seller_id = %(seller_id)s
          AND r.review_score <= 2
          AND r.review_comment_message IS NOT NULL
          AND r.review_creation_date < %(as_of)s
        ORDER BY r.review_creation_date DESC, r.review_id
        LIMIT 5
    """

    params = {"seller_id": seller_id, "as_of": as_of}

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM olist.sellers WHERE seller_id = %s", (seller_id,))
            if cursor.fetchone() is None:
                return None

            cursor.execute(stats_query, params)
            stats = cursor.fetchone()

            cursor.execute(recent_query, params)
            recent = cursor.fetchall()

    # Las tasas son None si el vendedor todavía no tiene datos antes de as_of.
    return {
        "seller_id": seller_id,
        "as_of": as_of,
        "orders": stats[0],
        "delivered_orders": stats[1],
        "late_rate": stats[2],
        "platform_late_rate": stats[3],
        "reviews": stats[4],
        "bad_review_rate": stats[5],
        "platform_bad_review_rate": stats[6],
        "recent_bad_reviews": [
            {
                "review_id": row[0],
                "score": row[1],
                "title": row[2],
                "message": row[3],
                "creation_date": row[4],
            }
            for row in recent
        ],
    }
