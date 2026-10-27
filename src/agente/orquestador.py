
from langgraph.graph import StateGraph, START, END

from src.agente.estado import EstadoAgente
from src.agente.nodos import (
    cargar_contexto,
    analizar_reclamo,
    validar_propuesta,
    decidir_siguiente_paso,
    decidir_segun_contexto
)



def detener_por_validacion(estado: EstadoAgente) -> dict:
    print("La propuesta fue rechazada por la validación.")
    return {}



def crear_orquestador(funcion_analisis=analizar_reclamo):
    # Construimos un nuevo grafo con el estado del agente.
    nuevo_grafo = StateGraph(EstadoAgente)

    # Registramos los nodos.
    nuevo_grafo.add_node("cargar_contexto", cargar_contexto)
    nuevo_grafo.add_node("analizar_reclamo", funcion_analisis)
    nuevo_grafo.add_node("validar_propuesta", validar_propuesta)
    nuevo_grafo.add_node(
        "detener_por_validacion",
        detener_por_validacion
    )

    # Definimos las transiciones.
    nuevo_grafo.add_edge(START, "cargar_contexto")

    # Si la reseña existe, continuamos con el análisis.
    # Si no existe, finalizamos el workflow.
    nuevo_grafo.add_conditional_edges(
        "cargar_contexto",
        decidir_segun_contexto,
        {
            "contexto_disponible": "analizar_reclamo",
            "resena_inexistente": END
        }
    )

    nuevo_grafo.add_edge("analizar_reclamo", "validar_propuesta")

    nuevo_grafo.add_conditional_edges(
        "validar_propuesta",
        decidir_siguiente_paso,
        {
            "propuesta_valida": END,
            "propuesta_invalida": "detener_por_validacion"
        }
    )

    nuevo_grafo.add_edge("detener_por_validacion", END)

    return nuevo_grafo.compile()



# Creamos la instancia principal del orquestador.
agente = crear_orquestador()


if __name__ == "__main__":

    # Preparamos el estado inicial del reclamo.
    estado_inicial: EstadoAgente = {
        "id_resena": "REV001",
        "contexto_caso": None,
        "accion_propuesta": None,
        "resultado_validacion": None
    }

    # Ejecutamos el grafo y observamos cada actualización.
    for actualizacion in agente.stream(
        estado_inicial,
        stream_mode="updates"
    ):
        print("Actualización del estado:")
        print(actualizacion)




