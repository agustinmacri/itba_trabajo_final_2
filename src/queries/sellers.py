from datetime import datetime

from src.database.connection import get_connection

# Mínimo de casos para mostrar una tasa del vendedor. Con menos, 1 de 1 daría 100% y el LLM
# lo leería como un patrón: la tasa vuelve None y quedan los conteos para ver por qué.
# Con 10, el vendedor tiene tasa en ~85% de los casos. Marcar al vendedor (flag_seller)
# debería pedir más: con 10 la tasa todavía varía ±11 puntos por azar.
MIN_SAMPLE_FOR_RATE = 10


def get_seller_history(seller_id: str, as_of: datetime) -> dict | None:
    # Todo se calcula solo con datos anteriores a as_of (el "hoy" del caso).
    # Si no, el agente vería reseñas escritas después del caso que está resolviendo.
    stats_query = """
        WITH seller_orders AS (
            SELECT DISTINCT order_id
            FROM olist.order_items
            WHERE seller_id = %(seller_id)s
        ),
        due_orders AS (
            -- Pedidos cuyo resultado ya se conocía a as_of: entregados, o con la fecha estimada
            -- vencida sin entregar. Los que todavía no vencían no cuentan ni a favor ni en contra.
            -- Los cancelados quedan afuera: no llegar porque se canceló no es un atraso.
            SELECT
                o.order_id IN (SELECT order_id FROM seller_orders) AS is_seller,
                -- COALESCE: si nunca llegó, la fecha es NULL y la comparación da NULL, no false.
                -- Sin esto, NOT is_delivered también da NULL y esos pedidos no se cuentan como vencidos.
                COALESCE(o.order_delivered_customer_date < %(as_of)s, FALSE) AS is_delivered,
                -- Si no había llegado a as_of, se usa as_of: ya está vencido aunque llegue después.
                -- Se compara por día: la fecha estimada viene a las 00:00, así que
                -- llegar ese mismo día a la tarde cuenta como a tiempo.
                CAST(COALESCE(
                    CASE WHEN o.order_delivered_customer_date < %(as_of)s THEN o.order_delivered_customer_date END,
                    %(as_of)s
                ) AS DATE) > CAST(o.order_estimated_delivery_date AS DATE) AS is_late
            FROM olist.orders o
            WHERE o.order_delivered_customer_date < %(as_of)s
               OR (o.order_estimated_delivery_date < %(as_of)s
                   AND o.order_status NOT IN ('canceled', 'unavailable'))
        ),
        reviews AS (
            SELECT
                BOOL_OR(r.order_id IN (SELECT order_id FROM seller_orders)) AS is_seller,
                MIN(r.review_score) <= 2 AS is_bad
            FROM olist.order_reviews r
            WHERE r.review_creation_date < %(as_of)s
            GROUP BY r.review_id
        ),
        -- order_stats, delivery_stats y review_stats resumen todo en una sola fila cada una
        -- (son agregaciones sin GROUP BY: devuelven una fila aunque no haya datos).
        -- Por eso el CROSS JOIN de abajo no multiplica filas.
        -- CAST(... AS INT) convierte true/false en 1/0: el promedio es la proporción.
        order_stats AS (
            SELECT COUNT(*) AS orders
            FROM olist.orders o
            JOIN seller_orders so ON so.order_id = o.order_id
            WHERE o.order_purchase_timestamp < %(as_of)s
        ),
        delivery_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE is_seller AND is_delivered) AS delivered_orders,
                COUNT(*) FILTER (WHERE is_seller AND NOT is_delivered) AS overdue_orders,
                CAST(ROUND(AVG(CAST(is_late AS INT)) FILTER (WHERE is_seller), 3) AS FLOAT) AS seller_late_rate,
                CAST(ROUND(AVG(CAST(is_late AS INT)), 3) AS FLOAT) AS platform_late_rate
            FROM due_orders
        ),
        review_stats AS (
            SELECT
                COUNT(*) FILTER (WHERE is_seller) AS reviews,
                CAST(ROUND(AVG(CAST(is_bad AS INT)) FILTER (WHERE is_seller), 3) AS FLOAT) AS seller_bad_review_rate,
                CAST(ROUND(AVG(CAST(is_bad AS INT)), 3) AS FLOAT) AS platform_bad_review_rate
            FROM reviews
        )
        SELECT
            os.orders,
            ds.delivered_orders,
            ds.overdue_orders,
            ds.seller_late_rate,
            ds.platform_late_rate,
            rs.reviews,
            rs.seller_bad_review_rate,
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

    delivered_orders, overdue_orders, reviews = stats[1], stats[2], stats[5]
    seller_late_rate = stats[3] if delivered_orders + overdue_orders >= MIN_SAMPLE_FOR_RATE else None
    seller_bad_review_rate = stats[6] if reviews >= MIN_SAMPLE_FOR_RATE else None

    # Las tasas del vendedor son None si no tiene suficientes datos antes de as_of.
    return {
        "seller_id": seller_id,
        "as_of": as_of,
        "orders": stats[0],
        "delivered_orders": delivered_orders,
        # Vencidos sin entregar a as_of: cuentan como atrasados.
        "overdue_orders": overdue_orders,
        "seller_late_rate": seller_late_rate,
        "platform_late_rate": stats[4],
        "reviews": reviews,
        "seller_bad_review_rate": seller_bad_review_rate,
        "platform_bad_review_rate": stats[7],
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
