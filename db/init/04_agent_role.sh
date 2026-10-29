#!/bin/bash
# Usuario de mínimo privilegio para el agente: lee olist, escribe app, no borra nada.
# El usuario dueño (POSTGRES_USER) queda para cargar datos y explorar.
set -euo pipefail

if [ -z "${AGENT_DB_PASSWORD:-}" ]; then
    echo "Falta AGENT_DB_PASSWORD en .env" >&2
    exit 1
fi

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v agent_user="${AGENT_DB_USER:-agent}" \
     -v agent_pw="$AGENT_DB_PASSWORD" <<'SQL'
CREATE ROLE :"agent_user" LOGIN PASSWORD :'agent_pw';

-- olist: solo lectura
GRANT USAGE ON SCHEMA olist TO :"agent_user";
GRANT SELECT ON ALL TABLES IN SCHEMA olist TO :"agent_user";

-- app: leer, insertar y actualizar; sin DELETE ni DROP
GRANT USAGE ON SCHEMA app TO :"agent_user";
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO :"agent_user";
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO :"agent_user";   -- para los SERIAL

-- tablas que se agreguen más adelante en app reciben los mismos permisos
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT SELECT, INSERT, UPDATE ON TABLES TO :"agent_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT USAGE ON SEQUENCES TO :"agent_user";
SQL
