from src.database.connection import get_connection


def get_review(review_id: str) -> dict | None:
    # Una reseña puede cubrir varios pedidos del mismo cliente: se agrupan sus order_id.
    # Puntaje, texto y fecha son los mismos en todas sus filas.
    query = """
        SELECT
            review_id,
            MIN(review_score),
            MIN(review_comment_title),
            MIN(review_comment_message),
            MIN(review_creation_date),
            ARRAY_AGG(order_id ORDER BY order_id)
        FROM olist.order_reviews
        WHERE review_id = %s
        GROUP BY review_id
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (review_id,))
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "review_id": row[0],
        "score": row[1],
        "title": row[2],
        "message": row[3],
        "creation_date": row[4],
        "order_ids": row[5],
    }
