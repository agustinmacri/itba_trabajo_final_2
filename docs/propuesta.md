# Propuesta TFI: agente de resolución de reclamos (Olist)

**Idea en una línea:** un agente que lee reseñas negativas de pedidos de e-commerce, verifica lo que dice el cliente contra la base de datos, y propone una acción (reembolso, reenvío, marcar al vendedor, responder o escalar). Las acciones con costo las aprueba un humano.

**Regla de diseño:** el LLM lee e interpreta, el código verifica y pone los límites (política), el humano aprueba lo que cuesta plata.

---

## 1. Por qué este caso y no otro

La prueba que usamos para elegir: **¿lo podría resolver un `if`?** Si la decisión depende solo de números ("stock < 10 → reponer"), una regla lo hace mejor, más barato y reproducible que un LLM. El LLM se justifica cuando hay que **leer e interpretar** algo para decidir.

| Caso | ¿Lo resuelve un `if`? | ¿Hay datos reales multi-tabla? | Veredicto |
|---|---|---|---|
| Reposición de stock | Sí (punto de reorden) | Raro en Kaggle, casi todo sintético | Débil: ganan las reglas |
| Fraude en transacciones | Mayormente, y ML le gana a un LLM | Features anonimizadas | Herramienta equivocada |
| Reclamos de consumidores (CFPB) | No, hay que leer el texto | Real, pero una sola tabla | Aceptable |
| **Reclamos de pedidos (Olist)** | **No: "llegó tarde" vs "llegó roto" vs "faltan ítems" está en el texto** | **Sí, ~9 tablas reales vinculadas** | **El mejor encaje** |

## 2. El dataset (verificado)

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Pedidos reales de sep-2016 a oct-2018. Lo descargamos y perfilamos:

| Tabla | Filas | Lo que importa |
|---|---|---|
| `orders` | 99k | estado, fechas de compra, entrega real y entrega **estimada** (se puede calcular "llegó tarde") |
| `order_reviews` | 99k filas / 98k reseñas | `review_score` 1-5 y `review_comment_message` (texto libre, en portugués). Una reseña puede cubrir varios pedidos (ver limitación 3) |
| `order_items` | 113k | productos y vendedor de cada pedido, precio, flete |
| `sellers`, `customers`, `products`, `payments` | 3k / 99k / 33k / 104k | historial de vendedor, región, medio de pago |
| `geolocation` | 1M | probablemente no la usemos |

**Las cifras que hacen viable el caso:**

- 14.396 reseñas malas (puntaje 1-2); **10.759 (75%) tienen texto**.
- Solo el **26%** de esas reseñas corresponde a pedidos entregados tarde según las fechas, y otro **15%** a pedidos sin fecha de entrega. En el ~60% restante las fechas no muestran ningún problema: la señal está **solo en el texto**.
- Temas en las reseñas malas (búsqueda aproximada por palabras clave): no llegó / atraso 34%, faltan ítems 8%, producto equivocado 8%, calidad 8%, roto 5%. **El 43% no coincide con ninguna palabra clave**: un set de reglas se pierde casi la mitad.
- El texto a veces **contradice los datos**: estado `delivered` pero el cliente escribe *"o produto não chegou"*.
- 634 vendedores tienen 30 pedidos o más, así que buscar patrones por vendedor tiene sentido.

**Limitaciones a tener en cuenta:**

1. **No hay nombres de producto**, solo categoría y dimensiones. "Me mandaron otro producto" no se puede verificar contra un título.
2. **Las reseñas no son por vendedor.** El 1,3% de los pedidos tiene más de un vendedor, y sumando la limitación 3, el **4,9% de las reseñas malas** involucra a más de un vendedor (caso borde para la evaluación: ¿a quién se marca?).
3. **Una reseña puede cubrir varios pedidos.** Hay 814 filas con `review_id` repetido, pero **no son duplicados**: son 789 reseñas que cubren varios pedidos del mismo cliente (Olist parte el carrito en un pedido por vendedor y el cliente reseña una sola vez). En los 789 casos es el mismo cliente con el mismo puntaje. **No se deduplica:** la clave de la tabla es `(review_id, order_id)`. Deduplicar por `review_id` borraría pedidos al azar. Entre las reseñas malas, 173 cubren más de un pedido.
4. **No existen tablas de reembolsos ni tickets.** Las acciones del agente se escriben en una tabla propia (`actions`).
5. **Los datos terminan en 2018.** Fijamos un "hoy" simulado (por ejemplo 2018-09-01).
6. **Las reseñas están en portugués.** El LLM las maneja bien, pero quien etiquete el set de evaluación tiene que leerlas.
7. **Licencia:** confirmar en la página de Kaggle antes de presentar.

## 3. Cómo funciona

### Disparador y cola de casos

**Una reseña = un caso = una ejecución del agente.** El agente no elige qué reseñas mirar: eso lo decide una regla simple.

```
1. DISPARADOR (código)          2. COLA (Postgres)            3. AGENTE (LLM)
llega una reseña nueva           tabla cases:                  toma UN caso pendiente
  └─ ¿puntaje ≤ 2? ──sí──►       case_id, order_id,            → lee el contexto,
       (o 3 con texto)           review_id, status             → propone acciones
  └─ no → se ignora              (pending / in_progress /      → escribe en `actions`
                                  awaiting_approval / done)    → siguiente caso
```

1. **El disparador es un filtro barato, no el LLM.** Una regla decide qué se convierte en caso (por ejemplo, puntaje ≤ 2: 14.396 reseñas). Correr el LLM sobre las 99k reseñas sería lento, caro e inútil para las 57k de 5 estrellas.
2. **Cada caso es una ejecución independiente**, como un ticket de soporte: su propio estado, sus llamadas a herramientas, sus acciones propuestas y su traza. Un solo agente mirando todas las reseñas juntas mezclaría casos y saturaría el contexto. Además, así la evaluación es directa: 30 casos etiquetados = 30 ejecuciones independientes.
3. **Como los datos son de 2018, simulamos la llegada.** Un botón **"simular día siguiente"** toma las reseñas cuya `review_creation_date` cae en el día siguiente del reloj simulado y las pasa por el disparador. Aparecen casos nuevos en la cola, el agente los procesa uno por uno, y los que implican plata quedan esperando aprobación en la UI.

**Mínimo para v1:** la tabla `cases`, el filtro del disparador, un loop "procesar siguiente caso" y el botón de simulación. No hace falta un scheduler ni webhooks.

### ¿No es esto un workflow?

Es la pregunta que nos van a hacer, y la respuesta corta es: **la parte que podría ser un workflow la hacemos como workflow a propósito.**

Si ya sabemos qué reclama el cliente y qué dicen los datos, la decisión *debería* ser determinística. "Faltan 2 de 3 ítems, entregado a tiempo, vendedor con 4× el promedio de faltantes" es una consulta a una tabla de política, no un juicio. Dejar eso librado al LLM significa que el mismo caso puede recibir un reembolso distinto el lunes y el martes, justo lo que no queremos cuando hay plata en juego.

**Tampoco dejamos que el LLM "elija qué investigar".** Las consultas de lectura son SQL barato y casi siempre útil: si el agente pudiera elegir, terminaría llamándolas todas, y cada llamada es un ida y vuelta extra con el LLM (más latencia y más tokens). Así que el código las corre todas antes y le entrega al LLM un paquete de contexto armado.

```
1. CÓDIGO     reseña + pedido + ítems + historial del vendedor  →  un paquete de contexto
2. LLM        lee todo → reclamo, nivel de confianza, llama a las herramientas de acción
3. CÓDIGO     cada herramienta de acción valida contra la tabla de política
4. HUMANO     aprueba lo que cuesta plata
```

| Capa | Quién | ¿Determinística? |
|---|---|---|
| **Reunir los hechos** (pedido, ítems, historial del vendedor) | Código (SQL), antes de llamar al LLM | Sí |
| **¿Qué reclama el cliente y le creemos?** (`"veio só 1 de 3"` → `faltan_items, 2 de 3`, verificado) | LLM | No, y por eso hay un LLM: el 43% de las reseñas malas no coincide con ninguna palabra clave |
| **¿Qué acciones están permitidas?** (tipo de acción, monto máximo, si necesita aprobación) | Código: tabla de política en configuración | Sí |

**Dónde el LLM sí decide (lo que un `if` no puede hacer):**

- **Interpretar la reseña:** cuál es el reclamo, cuántos hay, y si es un reclamo siquiera (puntaje 1 con *"adorei, chegou rápido"* → no actuar).
- **Sopesar la evidencia:** estado `delivered` pero el cliente escribe *"não chegou"*; *"faltou 1"* en un pedido de un solo ítem. ¿Le creemos al texto, a los datos, o escalamos?
- **Reseñas desordenadas:** dos reclamos en una reseña, ironía, amenaza legal, pedido con varios vendedores donde no está claro quién falló.
- **Actuar, no actuar o escalar**, y entre las acciones que la política permite (por ejemplo, reembolso parcial o reenvío), cuál, con qué parámetros y con una justificación escrita.

**La respuesta para el jurado:** juntamos el contexto de forma determinística porque es más barato y reproducible. La autonomía del agente está donde importa: interpretar el caso y elegir acciones con consecuencias reales, dentro de una política y con un humano para lo que cuesta plata. El disparador también es fijo, y está bien: todo agente arranca por algún lado.

### La objeción más fuerte: ¿por qué no clasificar con el LLM y decidir con `if`?

Para los casos claros, **clasificar + `if` es mejor**: más barato, 100% reproducible y fácil de testear. Nuestra tabla de política ya *es* ese `if`. Donde se complica:

- **Una categoría no alcanza.** "Faltan ítems" necesita *cuántos* y *cuáles*; "roto" necesita saber si es todo el pedido o un ítem. El clasificador se convierte en un extractor con esquema (reclamo, cantidades, confianza, amenaza legal, texto positivo con puntaje malo).
- **Las combinaciones se multiplican:** reclamo × verificado o contradicho × patrón del vendedor × entrega parcial × varios vendedores × dos reclamos en una reseña. El árbol de `if` crece y todo lo raro termina en un `else: escalar`.

**La pregunta real es qué tan grande es ese `else`.** Si es el 5% de los casos, gana clasificar + `if` y el agente es decoración. Si es el 30%, el agente se gana el lugar resolviendo lo que el árbol no puede. **No lo sabemos todavía**, así que no lo discutimos: lo medimos (sección 5). Clasificar + `if` es nuestro **baseline**, y si los números lo dicen, el diseño final es un **híbrido**: el `if` resuelve los casos claros y el agente solo toma lo que cae en el `else`.

**Si el baseline también usa un LLM, ¿cuál es la diferencia?** Quién decide. En el baseline el LLM es un **sensor**; en el agente es **quien decide**.

| | Baseline | Agente |
|---|---|---|
| Trabajo del LLM | **Describir**: llenar un formulario fijo | **Decidir**: elegir acciones y sus parámetros |
| Salida | JSON con esquema fijo: `{reclamo: "faltan_items", cantidad: 2, confianza: 0.9, amenaza_legal: false}` | Llamadas a `issue_refund`, `flag_seller`, `escalate_to_human`… |
| Quién elige la acción | `if` en Python sobre ese JSON | El LLM, dentro de la política |
| Llamadas al LLM | 1, sin herramientas | Varias, en un loop con herramientas |
| Si algo no encaja | Cae en el `else` → humano | Puede razonarlo y actuar o escalar con justificación |
| Si se equivoca | El `if` lo ejecuta a ciegas | La herramienta devuelve un error y el agente corrige |

El formulario siempre se puede agrandar (`segundo_reclamo`, `contradice_datos`, …) con más `if`. Cuanto más crece, más se parece al agente, solo que con la decisión escrita a mano. En el fondo la diferencia es **escribir todas las combinaciones de antemano o dejar que el LLM resuelva las que no se nos ocurrieron.** Eso es lo que mide la comparación.

### Contexto pre-cargado (SQL, lo corre el código antes del LLM)

| Consulta | Qué aporta |
|---|---|
| Pedido | estado, fechas (compra / entrega / estimada), pago |
| Ítems | cantidad de ítems, precio por ítem, vendedor de cada uno |
| Historial del vendedor | tasa de atraso y de reseñas malas **vs. el promedio de la plataforma**, más las 5 reseñas malas más recientes como ejemplos |

Es SQL puro. El LLM no cuenta nada: recibe un resumen chico y unos pocos ejemplos para leer.

### Herramientas del agente (las llama el LLM)

Las acciones son **herramientas reales** (function calling), no un JSON que el LLM devuelve al final y el código ejecuta. Esa diferencia importa: si fuera un JSON, sería salida estructurada, no uso de herramientas.

| Herramienta | Cuándo | ¿Aprobación humana? |
|---|---|---|
| `draft_customer_reply` | siempre que haya que responder | No (el humano decide si la envía) |
| `issue_refund` (total / parcial) | faltan ítems (parcial); no entregado o cancelado (total) | **Sí**: es plata |
| `reship_items` | producto roto o ítems faltantes | **Sí**: plata y logística |
| `flag_seller` | el historial muestra un patrón | **Sí**: afecta la relación con el vendedor |
| `escalate_to_human` | caso ambiguo, contradictorio o con amenaza legal ("vou processar!") | Le pasa el caso completo a una persona |
| (no actuar) | texto positivo a pesar del puntaje bajo, o ya resuelto | No: decidir no actuar también es una decisión |

**La validación vive adentro de cada herramienta.** Si una llamada viola la política, la herramienta no la registra y le devuelve un error al LLM (por ejemplo, *"reembolso total no permitido: el pedido llegó parcialmente"*). El agente tiene que corregir la propuesta o escalar. Eso es ida y vuelta real con las herramientas, y cubre los requisitos de "validación" y "manejo de errores" de la consigna.

**Opcional, una herramienta de lectura abierta:** `search_seller_reviews(seller_id, consulta)` ("¿alguien más se queja de lo mismo que este cliente?"). No se puede pre-cargar porque la consulta depende de lo que escribió el cliente. Entra solo si sobra tiempo; no es el argumento del proyecto.

### Ejemplo con una reseña real

> *"Comprei 3 itens e foi entregue somente 1 e não tenho com quem falar."* ("Compré 3 ítems, me entregaron solo 1 y no tengo con quién hablar.")

```
CONTEXTO (código):  3 ítems, R$ X cada uno · entregado a tiempo · vendedor: 12% de reclamos por faltantes vs 3% promedio
LLM LEE:            reclamo "faltan ítems (2 de 3)" → los datos lo respaldan (3 ítems), no es un atraso
LLM LLAMA:
  issue_refund(tipo="total")              → ❌ error: "reembolso total no permitido, el pedido llegó parcialmente"
  issue_refund(tipo="parcial", ítems=2)   → ✅ válido → ⏸ aprobación humana
  flag_seller(motivo="patrón de faltantes") → ✅ tasa > 2× el promedio → ⏸ aprobación humana
  draft_customer_reply(...)               → ✅ automático
```

Otra reseña sobre el mismo tipo de pedido, *"chegou tudo, mas demorou"* ("llegó todo, pero tardó"), recibe el mismo contexto pero termina en otro lado: atraso → solo una respuesta, sin humano. **Mismo contexto, distintas acciones según lo que el agente leyó.**

### Human-in-the-loop (HITL)

Las acciones con costo **quedan en pausa** hasta que una persona las **aprueba, modifica o rechaza**.

**Lo que pausa es la acción, no el agente.** El agente termina su ejecución y deja las acciones con costo en `actions` con estado `pending_approval`. Cuando una persona responde, se ejecuta esa acción y listo: **no se vuelve a llamar al LLM.** Aprobar es un `UPDATE`:

```sql
UPDATE app.actions
SET status = 'approved', decided_by = 'ana', final_params = '{"amount": 60.0}', decided_at = now()
WHERE action_id = 42 AND status = 'pending_approval';   -- el AND evita aprobar dos veces
```

Así nos ahorramos la parte más difícil de un HITL "de verdad": congelar al agente a mitad de camino y retomarlo horas después con todo su estado.

- **Solo pausa donde un error cuesta algo.** Pedir aprobación para una consulta de solo lectura parece artificial.
- **El humano ve contexto suficiente para decidir:** la acción propuesta, el razonamiento del agente y la evidencia (texto de la reseña, fechas, ítems).
- **La pausa sobrevive:** queda todo en Postgres, así que se puede aprobar al día siguiente o después de reiniciar la app. Esto cubre también el requisito de estado + persistencia.
- **La respuesta al cliente sale al final.** Si una persona rechaza el reembolso, el borrador que dice "te reembolsamos" ya no sirve. Por eso `draft_customer_reply` se envía después de que se decidieron las acciones con costo, y quien aprueba puede editarla.
- **El caso se cierra solo:** cuando no le quedan acciones en `pending_approval`, el caso pasa a `done`.
- **Tres niveles de autonomía** (automático / requiere aprobación / escalar), con el umbral de monto en configuración, no en el prompt. Es fácil de defender en la parte de diseño agéntico.

### Modelo de datos

Tres tablas propias en un schema `app`. Las tablas originales de Olist quedan en su propio schema, de solo lectura.

```
olist.*  (datos crudos, solo lectura)     app.*  (lo que produce el agente)
orders, order_reviews, ...      ──►       cases ──1:N──► actions
                                            └───1:N──► tool_calls
```

```sql
CREATE TABLE app.cases (
    case_id        SERIAL PRIMARY KEY,
    review_id      TEXT UNIQUE NOT NULL,      -- un caso por reseña: re-ejecutar el disparador no duplica
                                              -- sin order_id: una reseña puede cubrir varios pedidos;
                                              -- los pedidos del caso salen de olist.order_reviews
    status         TEXT NOT NULL,             -- pending / in_progress / awaiting_approval / done / escalated / failed
    agent_summary  TEXT,                      -- diagnóstico del agente ("faltan 2 de 3 ítems, patrón del vendedor")
    created_at     TIMESTAMPTZ DEFAULT now(),
    finished_at    TIMESTAMPTZ
);

CREATE TABLE app.actions (
    action_id      SERIAL PRIMARY KEY,
    case_id        INT REFERENCES app.cases,
    action_type    TEXT NOT NULL,             -- refund / reship / flag_seller / reply / escalate
    params         JSONB,                     -- lo que propuso el agente: {"amount": 120.5, "type": "partial"}
    reasoning      TEXT,                      -- por qué lo propuso (se le muestra a quien aprueba)
    status         TEXT NOT NULL,             -- proposed / pending_approval / approved / rejected / executed
    decided_by     TEXT,                      -- 'auto' o el nombre de la persona
    final_params   JSONB,                     -- lo que se ejecutó, si la persona lo modificó
    decided_at     TIMESTAMPTZ
);

CREATE TABLE app.tool_calls (
    call_id        SERIAL PRIMARY KEY,
    case_id        INT REFERENCES app.cases,
    step           INT,                       -- orden dentro de la ejecución
    tool_name      TEXT,
    input          JSONB,
    output         JSONB,
    latency_ms     INT,
    error          TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);
```

| Tabla | Responde | Requisito que cubre |
|---|---|---|
| `cases` | ¿Esta reseña ya se analizó? ¿En qué estado está? | Estado + persistencia |
| `actions` | ¿Qué propuso el agente, qué decidió la persona, qué se ejecutó? | HITL: aprobar / modificar / rechazar es `status` + `decided_by` + `final_params` |
| `tool_calls` | ¿Cómo llegó el agente a esa decisión, paso a paso? | Trazabilidad y depuración |

**Decisiones de diseño:**

1. **`UNIQUE (review_id)` en `cases`:** apretar "simular día siguiente" dos veces no crea casos duplicados (idempotencia).
2. **`params` y `final_params` separados:** si una persona cambia un reembolso del 100% al 50%, quedan las dos versiones. "¿Con qué frecuencia la persona corrige al agente?" es una métrica real para la evaluación.
3. **Un caso → varias acciones:** el ejemplo de ítems faltantes propone tres (reembolso + marcar vendedor + respuesta), y cada una se aprueba o rechaza por separado.
4. **`tool_calls` es también la herramienta de depuración:** si la evaluación dice que el caso 17 eligió mal, se leen sus llamadas y se ve en qué paso se desvió.

## 4. Alcance v1 (lo simple primero)

**Entra en v1:**

- Carga del dataset a Postgres (hecho: `docker compose up` con el dataset cargado).
- El paquete de contexto pre-cargado (3 consultas SQL) + las 5 herramientas de acción con validación adentro.
- La tabla `actions` con estados (`proposed`, `pending_approval`, `approved`, `rejected`, `executed`).
- Una interfaz simple (Streamlit): el caso a la izquierda, la propuesta y los botones de aprobar / modificar / rechazar a la derecha.
- El baseline (LLM extrae el reclamo + `if` sobre la tabla de política), que comparte casi todas las piezas con el agente.
- Evaluación agente vs. baseline sobre ~80 casos etiquetados a mano (detalle en la sección 5).
- Log de cada llamada a herramienta (trazabilidad).
- `docker compose up` levanta todo; `.env.example` sin credenciales reales.

**Queda afuera de v1 (y por qué está bien):**

| Fuera | Por qué |
|---|---|
| RAG / búsqueda vectorial | Es opcional en la consigna; los 5 ejemplos recientes cubren la necesidad |
| Preclasificar todas las reseñas con un LLM | Es una optimización; en v1 el agente lee ejemplos, no cuenta |
| `run_sql` libre | Herramientas fijas son más fáciles de testear y asegurar |
| Vouchers, investigación con el transportista | Las acciones principales ya muestran el mismo diseño |

**Regla:** primero la comparación (semanas 1 y 2), después v1 completo de punta a punta. Después, como mucho **una** mejora, y solo si la evaluación muestra un problema concreto que esa mejora arregla.

## 5. Evaluación: agente vs. baseline

Mismo contexto, mismo LLM y mismos casos para los dos sistemas. Lo único que cambia es clasificar + `if` contra el agente.

### Las respuestas correctas (lo que más importa)

- **Casos elegidos con la división incorporada.** Cada caso se marca **claro** o **ambiguo** *antes* de correr nada, con criterios fijos: la búsqueda por palabras clave no encontró nada, el texto contradice los datos, hay más de un reclamo, el pedido tiene varios vendedores, o hay amenaza legal. Si no, terminamos llamando "ambiguo" a lo que el agente justo acertó.
- **Etiqueta = el conjunto correcto de acciones + el parámetro clave** (por ejemplo: reembolso parcial de 2 ítems + marcar vendedor + respuesta), y también el reclamo principal. Así se ve si un sistema falló al **leer** o al **decidir**.
- **Dos personas etiquetan cada caso por separado** y después comparan. Si no coinciden, el caso es genuinamente ambiguo: se discute hasta acordar o se descarta. La tasa de acuerdo es un dato en sí ("ni los humanos coinciden más del X%").
- **Se etiqueta antes de ver lo que respondió cualquiera de los sistemas.** Si primero se ve la respuesta del agente, se etiqueta a su favor sin querer.
- **A veces hay más de una respuesta válida** (por ejemplo, reembolso parcial *o* reenvío, cuando la política permite los dos). Ahí se etiqueta **el conjunto de respuestas aceptables**, y cualquiera de ellas cuenta como correcta.

La respuesta correcta es **lo que haría un buen agente de soporte siguiendo nuestra política**, nunca lo que hizo alguno de los sistemas. Después se compara cada sistema contra esa respuesta. Ejemplo con 3 casos:

| Caso | Reseña | Respuesta correcta (a mano) | Baseline | Agente |
|---|---|---|---|---|
| 1 | *"comprei 3, chegou 1"* | reembolso parcial 2 ítems + respuesta | igual ✅ | igual ✅ |
| 2 | *"não chegou"*, estado `delivered` | escalar | reembolso parcial ❌ (el formulario decía "no recibido") | escalar ✅ |
| 3 | *"chegou só 1 de 3 e o que veio estava quebrado"* | reembolso parcial 2 + reenvío 1 | escala ⚠️ (no entró en el formulario) | reembolso parcial 2 ✅, le faltó el reenvío ⚠️ |

Caso 1 empate, caso 2 gana el agente, caso 3 aciertos parciales de los dos. Los aciertos parciales se resuelven con el **error ponderado** (abajo): los pesos deciden qué es peor, olvidarse de algo barato o mandarle a un humano un caso que se podía resolver.

### Tamaño: con 30 no alcanza para declarar un ganador

Con 30 casos, 3 de diferencia es ruido. Apuntamos a **~80 casos, mitad claros y mitad ambiguos**, en dos grupos:

- **dev (~30):** donde ajustamos el prompt, las categorías y las reglas. También sirve como prueba de regresión: cada cambio se vuelve a correr contra estos casos.
- **test (~50):** se corre **una sola vez**, al final. Ajustar contra el test es corregirse el propio examen.

**Mejorar el `if` mirando los errores no es hacer trampa, es parte del experimento,** siempre que pase solo en dev. Lo mismo vale para el prompt del agente: los dos aprenden de los mismos casos. El test mide lo que de verdad importa: **cómo se comporta cada sistema con casos que nadie miró.** Las reglas arreglan los problemas que ya vimos; la apuesta del agente es que resuelve los que todavía no vimos. Por eso la pregunta del test es:

> Después de mejorar los dos en dev, ¿el baseline arreglado sigue fallando en casos nuevos, o los cubre?

- **Si en test el baseline solo falla en el mismo tipo de casos que ya habíamos arreglado:** alcanzan las reglas, el agente aporta poco → híbrido con más reglas, y lo decimos.
- **Si en test aparecen rarezas nuevas que ninguna regla anticipó y el agente las resuelve:** ese es el argumento real para el agente. Las reseñas reales tienen una cola larga de casos raros y no se puede escribir una regla para cada uno de antemano.

### Un baseline justo: ni malo a propósito ni un monstruo

Si le ganamos a un `if` hecho a las apuradas, el jurado lo ve al instante. Si le ganamos a uno de 300 líneas, le ganamos a algo que nadie mantendría. Reglas:

1. **Mismo presupuesto de esfuerzo.** El baseline tiene el mismo tiempo de ajuste que el prompt del agente (X horas o N iteraciones sobre dev, fijado de antemano).
2. **El baseline lo arma alguien que no construye el agente**, y su trabajo es hacerlo ganar. Si el `if` lo escribe el equipo del agente, sin querer va a salir débil.
3. **Reportamos dos baselines:**
   - **Simple:** las categorías obvias + la tabla de política. Lo que un equipo escribiría en un día.
   - **Ajustado:** el mismo, después de corregir lo que falló en dev, dentro del presupuesto.

   Si el agente le gana a los dos, no hay discusión. Si solo le gana al simple, también es un resultado: con suficientes reglas se acerca, y el agente ahorra escribirlas y mantenerlas.
4. **Reportamos el tamaño del `if`**: cantidad de reglas y categorías, y cuánto tiempo llevó agregarlas. "El baseline necesitó 25 reglas más para igualar al agente en los casos ambiguos" dice mucho sobre el costo de mantenerlo, no solo sobre la precisión.

### Qué medimos

| Métrica | Por qué |
|---|---|
| **Acción correcta** (conjunto exacto) | el número principal |
| **Error ponderado** | no todos los errores cuestan lo mismo (tabla abajo) |
| **Reclamo leído bien** | separa los errores de lectura de los errores de decisión |
| **% escalado, y cuántos bien escalados** | escalar todo es seguro e inútil: hay que penalizarlo |
| **Consistencia** (mismo caso 5 veces, temperatura 0) | el agente tendría que estar cerca del 100% |
| **Costo y latencia por caso** | lo que pagamos por lo que gana el agente |
| **Tamaño del baseline** (reglas, categorías, horas) | lo que cuesta mantener las reglas que igualan al agente |

| Error | Peso |
|---|---|
| Reembolso / reenvío que no correspondía | 3 (plata perdida) |
| No reembolsar cuando correspondía | 2 (cliente enojado) |
| Escalar un caso claro | 1 (tiempo de una persona) |
| Solo la respuesta mal | 0,5 |

Los pesos se acuerdan en grupo **antes** de ver resultados, por la misma razón que las etiquetas.

### Cómo comparamos: caso por caso

Para cada caso anotamos si ganó el agente, ganó el baseline o empataron, **por separado para casos claros y ambiguos**:

```
                 claros (25)        ambiguos (25)
gana agente       1                   9
gana baseline     2                   2
empate           22                  14
```

(Números ilustrativos, no una predicción.) Con resultados así la historia se cuenta sola: en los claros empatan, así que conviene el `if`; en los ambiguos gana el agente, así que ahí se justifica → híbrido.

**La comparación más justa:** el baseline está obligado a escalar lo que no encaja en sus categorías. Esa pila va a un humano. La pregunta clave es: **de los casos que el baseline escala, ¿cuántos resuelve bien el agente sin humano?** Si resuelve bien, por ejemplo, el 60%, le ahorramos ese trabajo a la persona: un rol real y medible para el agente, aunque empate en los casos claros. Y sigue con HITL para todo lo que cuesta plata.

### ¿Qué pasa según quién gane?

| Resultado | Qué presentamos | Riesgo |
|---|---|---|
| **Gana el agente en los ambiguos** | Híbrido: `if` para lo claro, agente para lo difícil, con números | Bajo. Es el mejor caso. |
| **Empate en todo** | Híbrido igual: el agente toma solo lo que el baseline manda al `else` | Medio. Hay que justificar al agente por lo que saca de esa pila. |
| **Gana el baseline en todo** | "Medimos, y las reglas deciden mejor" | **Alto para la rúbrica:** la consigna exige una decisión agéntica (25 puntos). Un agente que pierde en todo es decoración. |

Incluso en el peor caso, la rúbrica da 20 puntos a evaluación y trazabilidad: un equipo que midió, encontró que ganan las reglas y lo dice con honestidad puntúa bien ahí. Para que no lleguemos a ese caso sin aviso está la alarma de la semana 1 (sección 6).

## 6. Plan de trabajo

La comparación necesita muy poco del proyecto, así que **va primero**, con un script, y el resto se construye alrededor del diseño que gane.

| La comparación necesita | Puede venir después |
|---|---|
| Olist cargado (Postgres o DuckDB local) | Streamlit |
| El paquete de contexto (las 3 consultas SQL) | HITL / flujo de aprobación |
| La tabla de política | Cola `cases` + "simular día siguiente" |
| Baseline: LLM extrae + `if` | Docker, README, `.env.example` |
| Agente: prompt + 5 herramientas que **solo escriben una fila** | Persistencia real de las aprobaciones |
| ~30 casos dev etiquetados | Los 50 casos de test |

Casi nada se tira: el cargador de contexto, el esquema de extracción, la tabla de política y el validador son comunes a los dos. El `if` del baseline pasa a ser el camino rápido del híbrido si así sale.

**Orden (~7 semanas si la entrega es ~5/12, a confirmar):**

1. **Semana 1:** carga de datos + `docker compose up` mínimo + paquete de contexto + tabla de política (acordada en grupo). **En paralelo, empezar a etiquetar** (no necesita código). **Alarma temprana:** aplicar las categorías y reglas a los casos dev (a mano o con el primer borrador del baseline) y medir **qué tan grande es la pila del `else`**. Si es el 2%, el agente casi no tiene trabajo y lo sabemos con 6 semanas de margen para cambiar de rumbo, no en la semana 6. Los números de la sección 2 (43% sin palabra clave, texto que contradice el estado) apuntan a que la pila es grande, pero es una hipótesis hasta medirla.
2. **Semana 2:** baseline + agente mínimo, los dos corridos sobre los casos dev. **Decisión de diseño:** agente, baseline o híbrido. Es la "arquitectura planificada" del Parcial 1. Con 30 casos, este resultado **orienta la decisión**, no la prueba.
3. **Semanas 3 a 5:** construir la app alrededor del ganador: cola, HITL, UI, persistencia, Docker. Parcial 2 = demo funcionando.
4. **Semana 6:** etiquetar los 50 casos de test (dev queda aparte), correr la evaluación final **una vez** y escribir los resultados. Estos son los números serios.
5. **Semana 7:** margen, README, presentación.

### Qué es fácil y qué es difícil

| Paso | Dificultad | Por qué |
|---|---|---|
| Cargar Olist en Postgres | ✅ Hecho | `docker compose up` carga todo en ~10 segundos, con un usuario `agent` de permisos mínimos. |
| Paquete de contexto (3 consultas SQL) | 🟢 Fácil | SQL simple. Solo el historial del vendedor con promedios pide un poco de cuidado. |
| Tabla de política + validador | 🟡 Media | El código es fácil; **ponernos de acuerdo en la política** no tanto: ¿cuándo es reembolso parcial, cuándo reenvío, cuándo marcamos al vendedor? |
| Esquema de extracción (LLM del baseline) | 🟡 Media | Diseñar bien el formulario e iterar el prompt hasta que devuelva JSON válido. |
| Baseline (`if`) | 🟢 → 🟡 | El simple sale rápido; el ajustado lleva lo que dé el presupuesto de esfuerzo. |
| Loop del agente con herramientas | 🟡 Media | Function calling, errores de las herramientas que vuelven al LLM, límite de iteraciones, log en `tool_calls`. Cada SDK tiene sus mañas. |
| **Etiquetar ~80 casos** | 🟡 Media, **🔴 riesgosa** | Leer portugués, revisar los datos, etiquetar de a pares, resolver desacuerdos. Es lento, aburrido y todo depende de esto. |
| Script de comparación + métricas | 🟢 Fácil | Con las etiquetas listas, es contar. Los pesos sí requieren discusión. |
| Cola `cases` + "simular día siguiente" | 🟢 Fácil | Reloj falso e inserciones idempotentes. |
| HITL (aprobar / modificar / rechazar) | 🟡 Media | Con la pausa en la acción y no en el agente, aprobar es un `UPDATE`. Lo delicado es "modificar" (cambiar parámetros) y no ejecutar nada dos veces. |
| Interfaz en Streamlit | 🟡 Media | Una UI básica sale rápido, pero Streamlit re-ejecuta todo el script en cada clic: manejar estado y botones de aprobar puede ser molesto. |
| **Docker + reproducibilidad** | 🟡 Media, **🔴 riesgosa** | De "anda en mi máquina" a "anda en la máquina del jurado": cargar el dataset en el contenedor, `.env`, healthchecks. Siempre lleva más de lo pensado. |
| Tests | 🟢 Fácil | El validador y las consultas se testean fácil; simular el LLM, un poco menos. |
| Skill + integración externa | 🟢 Fácil | Más que nada, empaquetar lo que ya existe. |
| README, resultados, presentación | 🟢 Fácil | Fácil, pero siempre se subestima. |

**Dónde se nos puede ir el tiempo:**

1. **El etiquetado.** No por difícil, sino porque es lo primero que se posterga ("etiquetamos después") y todo depende de él. **Arranca el día 1**, con una cuota fija por persona por semana.
2. **Acordar la política.** El código es una hora; la discusión entre cuatro sobre cuándo un reembolso es parcial puede llevar una semana. Se cierra en la semana 1 como v1 y se revisa después si hace falta.
3. **Docker.** Un `docker compose up` mínimo (Postgres con los datos cargados) en la semana 1, y crece desde ahí. Nunca para el final.

**Lo que parece difícil y no lo es:** el agente en sí. Con el contexto pre-cargado y solo herramientas de acción, el loop es corto.

**La trampa real no es técnica, es de coordinación:** cuatro personas, la cursada en paralelo con el trabajo, y un paso (el etiquetado) del que depende todo lo demás.

## 7. Cómo cubre los 8 componentes obligatorios

| Componente | Cómo lo cubrimos |
|---|---|
| Decisión agéntica, 2+ herramientas, validación, manejo de errores | El agente interpreta la reseña contra el contexto y llama a 5 herramientas de acción (function calling); cada herramienta valida contra la tabla de política y devuelve un error que el agente tiene que resolver |
| Skill reutilizable | Por ejemplo, "verificar un reclamo de cliente" |
| Estado + persistencia | Tabla `actions` en Postgres |
| HITL | `pending_approval` → aprobar / modificar / rechazar en la UI |
| Integración externa | Postgres, o notificación por Slack/email a quien aprueba |
| Interfaz usable sin tocar código | Streamlit |
| Ejecución reproducible | Repo + README + `.env.example` + Docker |
| Tests + set de evaluación + trazabilidad | ~80 casos etiquetados (dev + test), comparación contra el baseline, prueba de consistencia, tests de herramientas y del validador, log de llamadas |

## 8. Posible reparto (4 personas)

| Frente | Qué incluye |
|---|---|
| Datos + Docker | Carga a Postgres (hecha), consultas del paquete de contexto, `docker-compose` de la app completa |
| Agente | El paquete de contexto, la tabla de política, las 5 herramientas, el prompt, el loop del agente |
| HITL + interfaz | Tabla `actions`, flujo de aprobación, Streamlit |
| Evaluación + baseline + documentación | El baseline (extraer + `if`; su trabajo es hacerlo ganar), coordinar el etiquetado de los ~80 casos (todos etiquetan, de a pares), script de comparación, métricas, tests, README, presentación |

## Preguntas abiertas para el grupo

- [ ] ¿Confirmamos Olist o queremos evaluar otro dataset con el mismo criterio ("¿lo resuelve un `if`?")?
- [ ] ¿Qué LLM usamos (Gemini, como en el curso, o local con Ollama)?
- [ ] ¿Qué "hoy" simulado fijamos?
- [ ] ¿Quién toma cada frente?
- [ ] Confirmar la licencia del dataset en Kaggle.
- [ ] Acordar los pesos del error ponderado **antes** de ver resultados.
- [ ] ¿Quién lee mejor portugués? Esa persona revisa los desacuerdos de etiquetado.
- [ ] Confirmar la fecha de entrega (¿5/12?).
