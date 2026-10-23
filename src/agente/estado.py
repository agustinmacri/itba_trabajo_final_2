
from typing import TypedDict, Any


class EstadoAgente(TypedDict):
    id_resena: str
    contexto_caso: dict[str, Any] | None
    accion_propuesta: str | None
    resultado_validacion: bool | None
