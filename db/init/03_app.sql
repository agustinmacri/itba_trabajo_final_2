-- Tablas que escribe el agente. Ver el modelo de datos en la propuesta.

-- Un caso = una reseña. Una reseña puede cubrir varios pedidos:
-- los pedidos del caso salen de olist.order_reviews por review_id.
CREATE TABLE app.cases (
    case_id       SERIAL PRIMARY KEY,
    review_id     TEXT UNIQUE NOT NULL,      -- re-ejecutar el disparador no duplica casos
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'in_progress', 'awaiting_approval', 'done', 'escalated', 'failed')),
    agent_summary TEXT,                      -- diagnóstico del agente
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);

CREATE TABLE app.actions (
    action_id    SERIAL PRIMARY KEY,
    case_id      INT NOT NULL REFERENCES app.cases,
    action_type  TEXT NOT NULL
                 CHECK (action_type IN ('refund', 'reship', 'flag_seller', 'reply', 'escalate')),
    params       JSONB,                      -- lo que propuso el agente
    reasoning    TEXT,                       -- por qué (se le muestra a quien aprueba)
    status       TEXT NOT NULL
                 CHECK (status IN ('proposed', 'pending_approval', 'approved', 'rejected', 'executed')),
    decided_by   TEXT,                       -- 'auto' o el nombre de la persona
    final_params JSONB,                      -- lo que se ejecutó, si la persona lo modificó
    decided_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.tool_calls (
    call_id    SERIAL PRIMARY KEY,
    case_id    INT NOT NULL REFERENCES app.cases,
    step       INT NOT NULL,                 -- orden dentro de la ejecución
    tool_name  TEXT NOT NULL,
    input      JSONB,
    output     JSONB,
    latency_ms INT,
    error      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON app.cases (status);
CREATE INDEX ON app.actions (case_id);
CREATE INDEX ON app.actions (status);
CREATE INDEX ON app.tool_calls (case_id);
