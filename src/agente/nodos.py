
from src.agente.estado import EstadoAgente
from src.context import get_case_context


def cargar_contexto(estado: EstadoAgente) -> dict:
    id_resena = estado["id_resena"]

    contexto = get_case_context(id_resena)

    return {"contexto_caso": contexto}


def analizar_reclamo(estado: EstadoAgente) -> dict:
    contexto = estado["contexto_caso"]

    # Verificamos que la reseña exista.
    if contexto is None:
        raise ValueError("No se encontró la reseña en PostgreSQL")

    # El contexto real contiene los datos dentro de "review".
    resena = contexto["review"]
    calificacion = resena["score"]

    # Simulamos la decisión que posteriormente tomará el LLM.
    if calificacion <= 2:
        accion = "issue_refund"
    else:
        accion = "close_without_action"

    return {"accion_propuesta": accion}


def validar_propuesta(estado: EstadoAgente) -> dict:
    accion = estado["accion_propuesta"]

    # Acciones permitidas en el MVP.
    acciones_permitidas = {
        "issue_refund",
        "reship_items",
        "flag_seller",
        "draft_customer_reply",
        "escalate_to_human",
        "close_without_action"
    }

    # Comprobamos si la acción propuesta está permitida.
    es_valida = accion in acciones_permitidas

    return {"resultado_validacion": es_valida}


def decidir_siguiente_paso(estado: EstadoAgente) -> str:
    # Consultamos el resultado de la validación.
    es_valida = estado["resultado_validacion"]

    if es_valida is True:
        return "propuesta_valida"
    else:
        return "propuesta_invalida"


def decidir_segun_contexto(estado: EstadoAgente) -> str:
    # Si la reseña no existe, no podemos analizarla.
    if estado["contexto_caso"] is None:
        return "resena_inexistente"

    # Si existe, continuamos con el análisis.
    return "contexto_disponible"
