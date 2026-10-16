# Cómo levantar la base de datos

Guía paso a paso para tener Postgres con el dataset de Olist cargado en tu máquina.

## Requisitos (una sola vez)

1. Instalar **Docker Desktop**: https://www.docker.com/products/docker-desktop/ y dejarlo **abierto**.
2. Tener el repo clonado. Si ya lo tenías, actualizalo:

   ```bash
   git checkout main
   git pull
   ```

No hace falta bajar ninguna imagen a mano: Docker baja Postgres solo la primera vez.

## 1. Descargar los datos

Desde la carpeta del repo. No hace falta cuenta de Kaggle.

**Mac / Linux:**

```bash
curl -L -o data/olist.zip https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce
unzip data/olist.zip -d data/
rm data/olist.zip
```

**Windows (PowerShell):**

```powershell
curl.exe -L -o data\olist.zip https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce
tar -xf data\olist.zip -C data
del data\olist.zip
```

Tienen que quedar 9 archivos `.csv` en `data/`.

## 2. Crear el `.env`

- **Mac / Linux:** `cp .env.example .env`
- **Windows:** `copy .env.example .env`

Para probar en local, las contraseñas de ejemplo sirven. El `.env` no se sube a GitHub.

## 3. Levantar la base

```bash
docker compose up -d
```

La primera vez tarda un poco: baja la imagen y carga los datos (la carga en sí son ~10 segundos). Para ver si está lista:

```bash
docker ps
```

Tiene que decir `olist_db ... (healthy)`.

## 4. Probar que anda

```bash
docker exec -it olist_db psql -U olist -d olist -c "SELECT COUNT(*) FROM olist.orders;"
```

Tiene que dar **99441**.

Para entrar y escribir SQL:

```bash
docker exec -it olist_db psql -U olist -d olist
```

Para salir, `\q`. Si las filas largas se ven mal, `\x` las muestra campo por campo.

Una consulta para ver reseñas reales:

```sql
SELECT review_score, review_comment_message
FROM olist.order_reviews
WHERE review_score = 1 AND review_comment_message IS NOT NULL
LIMIT 5;
```

## Con una interfaz gráfica

DBeaver, la extensión PostgreSQL de VS Code o cualquier cliente de Postgres:

| Campo | Valor |
|---|---|
| Host | `localhost` |
| Puerto | `5432` (o el `POSTGRES_PORT` de tu `.env`) |
| Base | `olist` |
| Usuario | `olist` |
| Contraseña | la de `POSTGRES_PASSWORD` en tu `.env` |

## Desde Python (notebooks)

```python
# pip install pandas sqlalchemy psycopg2-binary
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("postgresql://olist:cambiar_esto@localhost:5432/olist")
pd.read_sql("SELECT order_status, COUNT(*) FROM olist.orders GROUP BY 1 ORDER BY 2 DESC", engine)
```

Cambiá la contraseña y el puerto si los modificaste en el `.env`.

## Qué hay adentro

| Schema | Qué tiene |
|---|---|
| `olist` | Los datos del dataset, solo lectura: `orders`, `order_items`, `order_reviews`, `order_payments`, `customers`, `sellers`, `products`, `product_category_name_translation` |
| `app` | Lo que escribe el agente: `cases`, `actions`, `tool_calls` (vacías al principio) |

| Usuario | Para qué |
|---|---|
| `olist` | Explorar y cargar datos (puede todo) |
| `agent` | El que usa el agente: lee `olist` y escribe en `app`, sin `DELETE`, `DROP` ni `CREATE` |

## Comandos útiles

| Comando | Qué hace |
|---|---|
| `docker compose stop` | Apaga la base (los datos quedan) |
| `docker compose up -d` | La vuelve a prender |
| `docker compose down -v` | Borra todo; la próxima vez recarga desde cero |
| `docker logs olist_db` | Muestra los logs (para ver errores) |

Todos se corren desde la carpeta del repo.

## Si algo falla

| Error | Qué hacer |
|---|---|
| *"Cannot connect to the Docker daemon"* | Docker Desktop no está abierto |
| *"port is already allocated"* | Ya tenés otro Postgres en el 5432. Poné `POSTGRES_PORT=5433` en el `.env` y volvé a hacer `docker compose up -d` |
| Cambiaste algo en `db/init/` y no pasa nada | Esos scripts solo corren con la base vacía: `docker compose down -v` y después `docker compose up -d` |
| *"password authentication failed"* | La contraseña no coincide con tu `.env`. Si cambiaste el `.env` después de crear la base, recreala con `down -v` |
| Windows: errores con `\r` en `docker logs olist_db` | Tu copia tiene finales de línea de Windows (CRLF). El repo ya fuerza LF, pero una copia vieja no se corrige sola: lo más simple es volver a clonar el repo y después `docker compose down -v` y `docker compose up -d` |
| `COPY` falla con *"No such file"* | Faltan los CSVs en `data/`: repetí el paso 1 y recreá la base con `down -v` |
