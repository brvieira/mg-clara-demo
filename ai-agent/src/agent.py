import asyncio
import json
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.memory.checkpointer import get_checkpointer
from src.memory.store import get_store
from src.graph.build import build_graph
from src.tools.mcp_client import MCP_SERVER_CONFIG
from src.tools.vector_search import vector_search_clausulas

_checkpointer = None
_store = None


def _get_connections():
    global _checkpointer, _store
    if _checkpointer is None:
        _checkpointer = get_checkpointer()
        _store = get_store()
    return _checkpointer, _store


def _turn_messages_since(messages: list, user_message: str) -> list:
    """Retorna as mensagens do turno atual (após a última mensagem do usuário)."""
    last_human_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage) and messages[i].content == user_message:
            last_human_idx = i
            break

    if last_human_idx is None:
        return []

    return messages[last_human_idx + 1:]


def _extract_turn_response_text(turn_messages: list) -> str:
    """Concatena o conteúdo de todas as AIMessage do turno — o modelo pode narrar
    (ex: acolhimento, menção a sinistro) antes de emitir uma tool call, e essa
    narração não deve ser descartada."""
    parts = [m.content for m in turn_messages if isinstance(m, AIMessage) and m.content]
    return "\n\n".join(parts)


def _extract_turn_tool_calls(turn_messages: list) -> list[dict]:
    """Extrai as tool calls feitas no turno atual."""
    calls = []

    for i, msg in enumerate(turn_messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                output = None
                for j in range(i + 1, len(turn_messages)):
                    tm = turn_messages[j]
                    if isinstance(tm, ToolMessage) and tm.tool_call_id == tc["id"]:
                        try:
                            output = json.loads(tm.content) if isinstance(tm.content, str) else tm.content
                        except (json.JSONDecodeError, TypeError):
                            output = tm.content
                        break
                calls.append({
                    "tool_name": tc["name"],
                    "input": tc["args"],
                    "output": output,
                })

    return calls


async def _invoke_async(thread_id: str, customer_id: str, message: str) -> dict:
    checkpointer, store = _get_connections()

    mcp = MultiServerMCPClient(MCP_SERVER_CONFIG)
    mcp_tools = await mcp.get_tools()

    # Todas as tools sob o mesmo tools_node: vector search local + MCP de oficinas
    all_tools = [vector_search_clausulas] + mcp_tools

    graph = build_graph(checkpointer, store, all_tools)

    result = await graph.ainvoke(
        {
            "customer_id": customer_id,
            "messages": [HumanMessage(content=message)],
            "long_term_facts": [],
            "customer_profile": None,
            "new_fact_to_save": None,
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    result_messages = result.get("messages", [])
    turn_messages = _turn_messages_since(result_messages, message)

    return {
        "response": _extract_turn_response_text(turn_messages) or result_messages[-1].content,
        "debug": {
            "long_term_facts": result.get("long_term_facts", []),
            "new_fact_saved": result.get("new_fact_to_save"),
            "tool_calls_made": _extract_turn_tool_calls(turn_messages),
        },
    }


def invoke(thread_id: str, customer_id: str, message: str) -> dict:
    """
    Invoca o agente ClaraSeg para uma mensagem do usuário.


    thread_id: identifica a sessão/conversa atual (memória de curto prazo)
    customer_id: identifica o cliente (memória de longo prazo e perfil)
    message: texto da mensagem do usuário

    Retorna dict com:
      - response (str): resposta do agente
      - debug (dict): dados para o painel de transparência da UI
        - long_term_facts: fatos recuperados do MongoDBStore
        - new_fact_saved: fato gravado nesta interação, ou None
        - tool_calls_made: lista de {tool_name, input, output} das tools chamadas neste turno
    """
    return asyncio.run(_invoke_async(thread_id, customer_id, message))
