-- Tablas crudas de Olist, cargadas desde los CSVs montados en /data.
-- geolocation (1M filas) queda afuera: el agente no la usa.

CREATE TABLE olist.customers (
    customer_id              TEXT PRIMARY KEY,
    customer_unique_id       TEXT NOT NULL,
    customer_zip_code_prefix TEXT,
    customer_city            TEXT,
    customer_state           TEXT
);

CREATE TABLE olist.sellers (
    seller_id              TEXT PRIMARY KEY,
    seller_zip_code_prefix TEXT,
    seller_city            TEXT,
    seller_state           TEXT
);

CREATE TABLE olist.products (
    product_id                 TEXT PRIMARY KEY,
    product_category_name      TEXT,
    product_name_lenght        INT,
    product_description_lenght INT,
    product_photos_qty         INT,
    product_weight_g           INT,
    product_length_cm          INT,
    product_height_cm          INT,
    product_width_cm           INT
);

CREATE TABLE olist.product_category_name_translation (
    product_category_name         TEXT PRIMARY KEY,
    product_category_name_english TEXT
);

CREATE TABLE olist.orders (
    order_id                      TEXT PRIMARY KEY,
    customer_id                   TEXT NOT NULL REFERENCES olist.customers,
    order_status                  TEXT NOT NULL,
    order_purchase_timestamp      TIMESTAMP,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

CREATE TABLE olist.order_items (
    order_id            TEXT NOT NULL REFERENCES olist.orders,
    order_item_id       INT  NOT NULL,
    product_id          TEXT NOT NULL REFERENCES olist.products,
    seller_id           TEXT NOT NULL REFERENCES olist.sellers,
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(10, 2),
    freight_value       NUMERIC(10, 2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE olist.order_payments (
    order_id             TEXT NOT NULL REFERENCES olist.orders,
    payment_sequential   INT  NOT NULL,
    payment_type         TEXT,
    payment_installments INT,
    payment_value        NUMERIC(10, 2),
    PRIMARY KEY (order_id, payment_sequential)
);

-- Una reseña puede cubrir varios pedidos del mismo cliente (Olist parte el carrito
-- en un pedido por vendedor). No son duplicados: la clave es (review_id, order_id).
CREATE TABLE olist.order_reviews (
    review_id               TEXT NOT NULL,
    order_id                TEXT NOT NULL REFERENCES olist.orders,
    review_score            INT  NOT NULL,
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

COPY olist.customers FROM '/data/olist_customers_dataset.csv' WITH (FORMAT csv, HEADER true);
COPY olist.sellers FROM '/data/olist_sellers_dataset.csv' WITH (FORMAT csv, HEADER true);
COPY olist.products FROM '/data/olist_products_dataset.csv' WITH (FORMAT csv, HEADER true);
COPY olist.product_category_name_translation FROM '/data/product_category_name_translation.csv' WITH (FORMAT csv, HEADER true);
COPY olist.orders FROM '/data/olist_orders_dataset.csv' WITH (FORMAT csv, HEADER true);
COPY olist.order_items FROM '/data/olist_order_items_dataset.csv' WITH (FORMAT csv, HEADER true);
COPY olist.order_payments FROM '/data/olist_order_payments_dataset.csv' WITH (FORMAT csv, HEADER true);
COPY olist.order_reviews FROM '/data/olist_order_reviews_dataset.csv' WITH (FORMAT csv, HEADER true);

-- Índices para las consultas del paquete de contexto.
CREATE INDEX ON olist.orders (customer_id);
CREATE INDEX ON olist.order_items (seller_id);
CREATE INDEX ON olist.order_reviews (order_id);
CREATE INDEX ON olist.order_reviews (review_creation_date);
