# Olist Claims Agent

Trabajo final del curso **Developer de Agentes de AI (ITBA)**.

Un agente que lee reseñas negativas de pedidos de e-commerce, verifica lo que dice el cliente contra la base de datos y propone una acción: reembolso, reenvío, marcar al vendedor, responder o escalar. Las acciones con costo las aprueba una persona.

**Regla de diseño:** el LLM lee e interpreta, el código verifica y pone los límites (política), el humano aprueba lo que cuesta plata.

📄 Propuesta completa (diseño, evaluación y plan de trabajo): [`docs/propuesta.md`](docs/propuesta.md)

## Dataset

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce): ~99k pedidos reales (2016-2018) en 9 CSVs vinculados: pedidos, ítems, reseñas, vendedores, clientes, productos, pagos, geolocalización y la traducción de categorías al inglés.

Los datos **no se suben al repo** (`data/` está en `.gitignore`). Cada uno los descarga localmente:

```bash
curl -L -o data/olist.zip https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce
unzip data/olist.zip -d data/
rm data/olist.zip
```

No hace falta cuenta de Kaggle para esta descarga.

## Base de datos (Postgres en Docker)

Requisitos: Docker Desktop abierto y los CSVs ya descargados en `data/`.

📘 Guía paso a paso (Mac y Windows, cómo probarla y qué hacer si algo falla): [`docs/base_de_datos.md`](docs/base_de_datos.md)

```bash
cp .env.example .env      # y cambiar la contraseña
docker compose up -d
```

La primera vez, Postgres crea las tablas y carga los CSVs solo (tarda unos segundos). Queda escuchando en `localhost:5432` (o el puerto que pongas en `POSTGRES_PORT`).

| Schema | Qué tiene |
|---|---|
| `olist` | Los datos del dataset, solo lectura. `geolocation` queda afuera porque el agente no la usa. |
| `app` | Lo que escribe el agente: `cases`, `actions`, `tool_calls`. |

Hay dos usuarios, con las contraseñas que pongas en `.env`:

| Usuario | Para qué | Permisos |
|---|---|---|
| `olist` (`POSTGRES_USER`) | Cargar datos y explorar | Dueño de todo |
| `agent` (`AGENT_DB_USER`) | El agente | `olist`: solo lectura. `app`: leer, insertar y actualizar; **sin** `DELETE`, `DROP` ni `CREATE` |

El agente se conecta siempre con `agent`: si un bug o el LLM intenta algo raro, la base lo frena.

Para entrar con `psql`:

```bash
docker exec -it olist_db psql -U olist -d olist
```

> ⚠️ **Los scripts de `db/init/` solo corren cuando la base está vacía.** Si cambiás un `.sql` y no pasa nada, borrá el volumen y volvé a levantar: `docker compose down -v && docker compose up -d`. Esto borra también lo que haya escrito el agente en `app`.

**Ojo con las reseñas:** una misma reseña puede cubrir varios pedidos del mismo cliente (Olist parte el carrito en un pedido por vendedor). Por eso `order_reviews` tiene clave `(review_id, order_id)` y no se deduplica por `review_id`.

## Estructura

```
olist_claims_agent/
├── data/              # CSVs de Olist (locales, no se versionan)
├── db/init/           # SQL y scripts que Postgres corre al crear la base
├── docs/              # propuesta y guías
├── notebooks/         # exploración y pruebas
├── src/
│   ├── database/      # conexión a Postgres (usuario agent)
│   ├── queries/       # consultas de lectura: las corre el código, no el LLM
│   ├── context.py     # arma el paquete de contexto de cada caso, a la fecha de la reseña
│   └── serialization.py  # único punto de conversión a JSON
├── tests/
├── docker-compose.yml
└── .env.example
```

📐 Cómo se llaman las funciones entre sí y qué devuelve el paquete de contexto: [`docs/arquitectura.md`](docs/arquitectura.md)

**`queries/` no son herramientas del LLM.** Las consultas de lectura las corre el código antes de llamar al LLM y se le pasan como contexto. Las herramientas (*tools*) son las acciones que el LLM elige (`issue_refund`, `flag_seller`, …) e irán en `src/tools/`. Ver `docs/propuesta.md`, sección 3.

### Requisitos de Python

**Python 3.10 o más nuevo** (usamos 3.12; está fijado en `.python-version`). El código usa tipos como `dict | None`, que no existen en versiones anteriores. Ojo en Mac: el `python3` que viene con el sistema suele ser 3.9 y falla al importar con `TypeError: unsupported operand type(s) for |`. Para chequear:

```bash
python3 --version
```

Si da 3.9 o menos, instalá una versión nueva (por ejemplo con `brew install python@3.12` o `pyenv install 3.12`) y creá el entorno con ella:

```bash
python3.12 -m venv .venv
source .venv/bin/activate      # en Windows: .venv\Scripts\activate
```

### Tests

Necesitan la base levantada (`docker compose up -d`):

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Estado

🚧 En construcción: base de datos lista; falta el agente.
