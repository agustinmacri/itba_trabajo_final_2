
from src.agente.orquestador import agente

from langgraph.graph import StateGraph, START, END
from src.agente.estado import EstadoAgente
from src.agente.nodos import validar_propuesta, decidir_siguiente_paso


def test_reclamo_con_propuesta_valida():
    # Preparamos el estado inicial.
    estado_inicial = {
        "id_resena": "REV001",
        "contexto_caso": None,
        "accion_propuesta": None,
        "resultado_validacion": None
    }

    # Ejecutamos el workflow completo.
    estado_final = agente.invoke(estado_inicial)

    # Verificamos los resultados.
    assert estado_final["contexto_caso"] is not None
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

