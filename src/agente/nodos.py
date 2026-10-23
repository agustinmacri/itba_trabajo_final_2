
from src.agente.estado import EstadoAgente



def cargar_contexto(estado: EstadoAgente) -> dict:
    id_resena = estado["id_resena"]

    # Simulamos los datos recuperados de PostgreSQL.
    contexto = {
        "id_resena": id_resena,
        "calificacion": 1,
        "comentario": "El producto llegó roto",
        "estado_pedido": "delivered"
    }

    return {"contexto_caso": contexto}


def analizar_reclamo(estado: EstadoAgente) -> dict:
    contexto = estado["contexto_caso"]

    # Verificamos que exista información del reclamo.
    if contexto is None:
        raise ValueError("No se encontró el contexto del reclamo")

    calificacion = contexto["calificacion"]

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
