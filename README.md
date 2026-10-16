# Olist Claims Agent

Trabajo final del curso **Developer de Agentes de AI (ITBA)**.

Un agente que lee reseñas negativas de pedidos de e-commerce, verifica lo que dice el cliente contra la base de datos y propone una acción: reembolso, reenvío, marcar al vendedor, responder o escalar. Las acciones con costo las aprueba una persona.

**Regla de diseño:** el LLM lee e interpreta, el código verifica y pone los límites (política), el humano aprueba lo que cuesta plata.

## Dataset

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce): ~99k pedidos reales (2016-2018) en 9 CSVs vinculados: pedidos, ítems, reseñas, vendedores, clientes, productos, pagos, geolocalización y la traducción de categorías al inglés.

Los datos **no se suben al repo** (`data/` está en `.gitignore`). Cada uno los descarga localmente:

```bash
curl -L -o data/olist.zip https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce
unzip data/olist.zip -d data/
rm data/olist.zip
```

No hace falta cuenta de Kaggle para esta descarga.

## Estructura

```
olist_claims_agent/
├── data/        # CSVs de Olist (locales, no se versionan)
└── notebooks/   # exploración y pruebas
```

## Estado

🚧 En construcción: estructura inicial del proyecto.
