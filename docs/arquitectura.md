# Arquitectura del código

Cómo está armado el código, cómo se llaman las funciones entre sí y qué devuelven. Para el *por qué* del diseño, ver [`propuesta.md`](propuesta.md); para levantar la base, [`base_de_datos.md`](base_de_datos.md).

> **Mantener al día:** si agregás una función o cambiás lo que devuelve el paquete de contexto, actualizá este archivo en el mismo PR.

## La idea en una línea

**El código junta los hechos, el LLM interpreta, la política pone los límites.** Por ahora está construida la primera parte: el paquete de contexto que va a recibir el LLM para cada caso.

## Archivos

```
src/
├── database/connection.py   get_connection(): abre una conexión a Postgres con el usuario "agent"
├── queries/                 lectura de la base (la corre el código, no el LLM)
│   ├── reviews.py           get_review
│   ├── orders.py            get_order, get_order_items, get_order_payments
│   └── sellers.py           get_seller_history
├── context.py               get_case_context: arma el paquete de un caso
└── serialization.py         to_json: pasa el paquete a JSON para el LLM

tests/                       un archivo por módulo; necesitan la base levantada
```

## Cómo se llaman entre sí

Todo arranca con un `review_id`. `get_case_context` llama al resto en este orden:

```
get_case_context(review_id)
│
├── 1. get_review(review_id)
│      → puntaje, texto, fecha y la lista de order_ids
│      → si no existe: devuelve None y termina
│
├── 2. as_of = fecha de la reseña          ← el "hoy" del caso, se usa en todo lo que sigue
│
├── 3. por cada order_id de la reseña:
│      ├── get_order(order_id, as_of)
│      │     → el pedido como estaba ese día (fechas posteriores ocultas, estado reconstruido)
│      │     → None si se compró después de la reseña → se saltea
│      ├── get_order_items(order_id)
│      │     → productos, vendedor, precio, flete, categoría
│      ├── get_order_payments(order_id)
│      │     → total pagado y cada pago
│      └── items_missing = ¿no tiene ítems?
│
├── 4. por cada vendedor que apareció en los ítems:
│      └── get_seller_history(seller_id, as_of)
│            → sus números vs. la plataforma y 5 reseñas malas recientes, todo antes de as_of
│
└── 5. devuelve el paquete (+ orders_missing si no quedó ningún pedido)

Después, para mandarlo al LLM:
to_json(paquete) → texto JSON
```

Cada función de `queries/` abre y cierra su propia conexión. Cuesta ~6 ms por conexión, un 15-20% del tiempo de un caso; lo que más tarda es `get_seller_history` (calcula los promedios de la plataforma en cada llamada). Si en algún momento molesta, se pasa la conexión como parámetro o se usa un pool.

## Qué sale al final

Caso real `00397dc753e8c52a2dd4d73a20b88ae7`, recortado:

```jsonc
{
  "as_of": "2018-03-21T00:00:00",              // el "hoy" del caso
  "orders_missing": false,
  "review": {
    "score": 1,
    "message": "não recebi o produto",
    "order_ids": ["543ab312…"]
  },
  "orders": [{
    "order_status": "shipped",                  // el 21/03 seguía en camino (llegó el 02/04)
    "purchase_date": "2018-02-28T22:42:01",
    "carrier_date": "2018-03-02T00:15:04",      // el vendedor despachó en 2 días
    "estimated_delivery_date": "2018-03-19",    // ya estaba vencido hace 2 días
    "delivered_date": null,                     // oculto: es del futuro
    "items": [{"price": 510.0, "freight_value": 70.44, "category": "relogios_presentes", "seller_id": "7d13…"}],
    "payments": {"total": 580.44, "payments": [{"type": "credit_card", "installments": 8, "value": 580.44}]},
    "items_missing": false
  }],
  "sellers": [{
    "orders": 97, "delivered_orders": 22, "overdue_orders": 7, "reviews": 23,
    "seller_late_rate": 0.241,       "platform_late_rate": 0.079,
    "seller_bad_review_rate": 0.174, "platform_bad_review_rate": 0.148,
    "recent_bad_reviews": [{"message": "Ñ compriu seu prazo de entrega", "creation_date": "2018-03-17"}, …]
  }]
}
```

Con solo esto, un LLM debería poder razonar algo como: *"el cliente dice que no llegó; el pedido está vencido hace 2 días y sigue en camino, así que tiene razón. El vendedor despachó en 2 días, así que este atraso es del transportista. Pero el vendedor tiene 7 pedidos vencidos y un 24% de atraso contra un 7,9% de la plataforma: puede haber un patrón, aunque esa tasa mezcla atrasos del vendedor y del transportista."*

Para verlo con cualquier reseña:

```python
from src.context import get_case_context
from src.serialization import to_json

print(to_json(get_case_context("00397dc753e8c52a2dd4d73a20b88ae7")))
```

## Reglas que hay que respetar al tocar el código

1. **`queries/` no son herramientas del LLM.** Las consultas de lectura las corre el código antes de llamar al LLM. Las herramientas (*tools*) son las acciones que elige el LLM y van en `src/tools/`.
2. **Todo a la fecha de la reseña (`as_of`).** El estado final de un pedido es información del futuro: en el 23% de las reseñas malas con texto, el pedido llegó *después* de que el cliente escribió. Cualquier dato nuevo del contexto que cambie con el tiempo tiene que respetar `as_of`. Detalle en la limitación 9 de la propuesta.
3. **JSON solo en `to_json`.** Las consultas devuelven tipos de Python (`datetime`, etc.); la conversión a JSON se hace en un único lugar, al final.
4. **Desconocido no es lo mismo que vacío.** Si falta un dato, se marca (`items_missing`, `orders_missing`, `payments.total = None`) en vez de devolver una lista vacía o un 0 que el LLM leería como "no compró nada" o "no pagó nada".
5. **Las cuentas las hace SQL.** El LLM recibe tasas y conteos ya calculados, nunca filas para contar.
6. **Sin muestra suficiente, no hay tasa.** Las tasas del vendedor vuelven `None` si tiene menos de `MIN_SAMPLE_FOR_RATE` (10) reseñas o pedidos vencidos/entregados: con 1 de 1, el LLM leería un 100% como patrón. Los conteos quedan para que se vea por qué. Con 10, el vendedor tiene tasa en ~85% de los casos.
7. **Estilo SQL:** palabras clave en mayúscula, `CAST(x AS DATE)` (no `::`), con el tipo en mayúscula.

## Datos que el contexto no puede reconstruir

| Dato | Qué pasa |
|---|---|
| Estado de pedidos `canceled` / `unavailable` | No hay fecha de cancelación: queda el estado final. Afecta también a la tasa de atraso: un pedido vencido a `as_of` que se canceló después queda fuera del cálculo |
| Lo que pasó el mismo día de la reseña | `review_creation_date` no tiene hora: queda oculto (3% de los casos) |
| Pagos | `order_payments` no tiene fecha: se asume que son de la compra |
| Reseñas vinculadas a compras posteriores | En la historia del vendedor, una reseña solo cuenta vía pedidos comprados antes de ella (afecta a 8 pares reseña-vendedor) |
| Ítems de pedidos `unavailable` | 775 pedidos no tienen ítems; no sabemos si se borraron o nunca se registraron |
| Atrasos en pedidos con varios vendedores | Cuentan para todos: la fecha de despacho es por pedido, no por ítem |

## Qué falta construir

| Pieza | Dónde va a ir |
|---|---|
| Tabla de política (cuándo reembolsar, reenviar, marcar) | Por definir en grupo. Ojo: con 10 datos la tasa del vendedor todavía varía ±11 puntos por azar, así que `flag_seller` debería pedir una muestra mayor (20-30) que la que se usa para mostrar la tasa |
| Baseline: LLM extrae el reclamo + `if` | Por definir |
| Agente: prompt + las 6 acciones (incluida `close_without_action`) | `src/tools/`. Ojo: el `CHECK` de `app.actions.action_type` en `db/init/03_app.sql` todavía no tiene `close`; agregarlo en ese PR |
| Cola de casos, aprobación humana, interfaz | Tablas `app.*` (ya creadas) + Streamlit |
| Evaluación agente vs. baseline | Issue #8 para los casos |
