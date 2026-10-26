import json
from datetime import date, datetime
from decimal import Decimal


def _to_json_value(value):
    # json.dumps llama a esta función con los tipos que no sabe convertir.
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"No se puede pasar a JSON: {type(value).__name__}")


def to_json(data) -> str:
    # Único lugar donde se convierte a JSON (para el LLM y para app.tool_calls).
    # ensure_ascii=False mantiene "não chegou" legible.
    return json.dumps(data, default=_to_json_value, ensure_ascii=False)
