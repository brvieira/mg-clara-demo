from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.store.mongodb import MongoDBStore

from src.graph.state import AgentState
from src.graph.nodes import load_memory, make_reasoning, save_memory


def build_graph(checkpointer: MongoDBSaver, store: MongoDBStore, all_tools: list):
    """
    Compila o grafo com o seguinte fluxo por turno:

    START → load_memory → reasoning → [tools_condition]
                                           ↓ tool call(s)
                                      tools_node → reasoning  (loop até não haver mais tool calls)
                                           ↓ sem tool calls
                                      save_memory → END

    load_memory é um nó fixo: executa uma vez por turno, antes do reasoning.
    O loop reasoning ⇄ tools_node permite cadeias de tool calls — ex: busca de cláusula
    seguida de busca de oficina na mesma interação, sem nova mensagem do cliente.
    save_memory é um nó fixo: executa uma vez por turno, ao final.
    """
    reasoning_node = make_reasoning(all_tools)
    tool_node = ToolNode(all_tools)

    builder = StateGraph(AgentState)

    builder.add_node("load_memory", load_memory)
    builder.add_node("reasoning", reasoning_node)
    builder.add_node("tools_node", tool_node)
    builder.add_node("save_memory", save_memory)

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "reasoning")

    # tools_condition: roteia para "tools_node" se o LLM emitiu tool call(s),
    # ou para END (remapeado para "save_memory") se emitiu resposta final.
    builder.add_conditional_edges(
        "reasoning",
        tools_condition,
        {"tools": "tools_node", END: "save_memory"},
    )

    builder.add_edge("tools_node", "reasoning")  # fecha o loop
    builder.add_edge("save_memory", END)

    return builder.compile(checkpointer=checkpointer, store=store)
