
from src.agente.orquestador import agente

from langgraph.graph import StateGraph, START, END
from src.agente.estado import EstadoAgente
from src.agente.nodos import validar_propuesta, decidir_siguiente_paso



def test_reclamo_con_propuesta_valida():
    # Utilizamos una reseña real del dataset Olist.
    estado_inicial = {
        "id_resena": "00397dc753e8c52a2dd4d73a20b88ae7",
        "contexto_caso": None,
        "accion_propuesta": None,
        "resultado_validacion": None
    }

    # Ejecutamos el workflow completo con LangGraph.
    estado_final = agente.invoke(estado_inicial)

    # Verificamos que se haya recuperado el contexto real.
    contexto = estado_final["contexto_caso"]

    assert contexto is not None
    assert contexto["review"]["score"] == 1

    # El pedido todavía estaba en camino cuando se escribió la reseña.
    assert contexto["orders"][0]["order_status"] == "shipped"

    # Verificamos la propuesta simulada y su validación básica.
    assert estado_final["accion_propuesta"] == "issue_refund"
    assert estado_final["resultado_validacion"] is True



def test_reclamo_con_propuesta_invalida():

    # Simulamos una propuesta incorrecta del LLM.
    def proponer_accion_invalida(estado: EstadoAgente) -> dict:
        return {"accion_propuesta": "accion_inexistente"}

    # Construimos un grafo reducido para la prueba.
    grafo = StateGraph(EstadoAgente)

    grafo.add_node("proponer_accion", proponer_accion_invalida)
    grafo.add_node("validar_propuesta", validar_propuesta)

    grafo.add_edge(START, "proponer_accion")
    grafo.add_edge("proponer_accion", "validar_propuesta")

    grafo.add_conditional_edges(
        "validar_propuesta",
        decidir_siguiente_paso,
        {
            "propuesta_valida": END,
            "propuesta_invalida": END
        }
    )

    agente_prueba = grafo.compile()

    estado_inicial: EstadoAgente = {
        "id_resena": "REV001",
        "contexto_caso": None,
        "accion_propuesta": None,
        "resultado_validacion": None
    }

    estado_final = agente_prueba.invoke(estado_inicial)

    assert estado_final["accion_propuesta"] == "accion_inexistente"
    assert estado_final["resultado_validacion"] is False


def test_resena_inexistente():
    # Preparamos un identificador que no existe en Olist.
    estado_inicial = {
        "id_resena": "RESENA_INEXISTENTE",
        "contexto_caso": None,
        "accion_propuesta": None,
        "resultado_validacion": None
    }

    # Ejecutamos el orquestador completo.
    estado_final = agente.invoke(estado_inicial)

    # No se encontró información del reclamo.
    assert estado_final["contexto_caso"] is None

    # El análisis y la validación no se ejecutaron.
    assert estado_final["accion_propuesta"] is None
    assert estado_final["resultado_validacion"] is None

