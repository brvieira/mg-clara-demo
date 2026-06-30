import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.store.base import BaseStore

from src.config import LLM_MODEL, CUSTOMER_PROFILE_COLLECTION
from src.db import get_db
from src.graph.state import AgentState

llm = ChatOpenAI(model=LLM_MODEL, temperature=0)

SYSTEM_PROMPT = """Você é Clara, agente de atendimento da Vivaz Seguros, uma seguradora de auto e residencial.
Responda sempre em português, de forma clara, objetiva e empática.

Você tem ferramentas disponíveis — use-as da seguinte forma:
- vector_search_clausulas: use SEMPRE que o cliente relatar um acidente, sinistro ou incidente com o veículo/imóvel, ou perguntar sobre coberturas, exclusões, franquia, prazos de acionamento ou qualquer condição contratual. Passe o parâmetro category ("auto", "residencial" ou "sinistro_geral") se for possível inferir do perfil do cliente.
- buscar_oficinas_proximas: quando o cliente precisar de uma oficina parceira para reparo ou vistoria. Use o CEP do perfil do cliente se disponível.
- consultar_agenda_pericia: quando o cliente quiser agendar uma perícia em uma oficina específica.

Responda sempre com base nas informações retornadas pelas ferramentas, e não invente respostas. Se a ferramenta não retornar resultados, informe o cliente de forma clara e empática.
Para perguntas sobre dados já disponíveis no perfil (número de apólice, status de sinistro, dados cadastrais), responda diretamente sem acionar ferramentas.
Não invente coberturas nem nomes de oficinas — use apenas o que as ferramentas retornarem.
Procure sempre por fatos já conhecidos sobre o cliente (perfil, fatos duradouros) antes de acionar ferramentas, e utilize essas informações para contextualizar suas respostas. Se não houver informações suficientes, peça educadamente mais detalhes ao cliente.
Sempre inicie a conversa com uma saudação e se apresente como Clara, agente de atendimento da Vivaz Seguros.
Sempre que possível, utilize o nome do cliente (disponível no perfil) para tornar a conversa mais pessoal e empática.
SEMPRE basei suas resposta em fatos duradouros sobre o cliente, e valide se a questão se relaciona a algum fato duradouro antes de acionar ferramentas. Se houver um fato duradouro relevante, mencione-o na resposta, caso contrario, peça mais informações ao cliente para poder ajudá-lo.
"""

EXTRACT_FACT_PROMPT = """Com base na última mensagem do usuário e na resposta que você acabou de dar, identifique se há um fato NOVO e DURADOURO sobre o cliente que deva ser persistido para consultas futuras.

Exemplos de fatos duradouros: mudança de veículo, mudança de endereço, preferência de contato, reclamação recorrente.
NÃO é um fato duradouro: uma pergunta sobre cobertura, o status de um sinistro, saudações.

Responda APENAS com um JSON válido no formato abaixo, sem nenhum texto adicional:
- Se houver fato novo: {{"has_fact": true, "key": "identificador_curto", "fact": "descrição do fato em uma frase"}}
- Se não houver: {{"has_fact": false}}"""


# --- helpers ---

def _build_system_context(state: AgentState) -> str:
    profile = state.get("customer_profile") or {}
    long_term_facts = state.get("long_term_facts", [])

    profile_text = json.dumps(profile, ensure_ascii=False, indent=2) if profile else "Não disponível"
    facts_text = (
        "\n".join(f"- {f.get('fact', '')}" for f in long_term_facts)
        if long_term_facts
        else "Nenhum fato registrado."
    )

    return f"""{SYSTEM_PROMPT}

--- PERFIL DO CLIENTE ---
{profile_text}

--- FATOS CONHECIDOS SOBRE O CLIENTE (memória de longo prazo) ---
{facts_text}"""


def _extract_fact(last_human: str, response_content: str) -> dict | None:
    extract_messages = [
        SystemMessage(content=EXTRACT_FACT_PROMPT),
        HumanMessage(content=f"Mensagem do usuário: {last_human}\nResposta dada: {response_content}"),
    ]
    fact_response = llm.invoke(extract_messages)
    try:
        parsed = json.loads(fact_response.content)
        if parsed.get("has_fact"):
            return {
                "_key": parsed.get("key", "fact"),
                "fact": parsed["fact"],
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
    except (json.JSONDecodeError, KeyError):
        pass
    return None


# --- nós do grafo ---

def load_memory(state: AgentState, store: BaseStore) -> dict:
    """Nó fixo — executa sempre, antes do reasoning, em todo turno."""
    customer_id = state["customer_id"]

    items = store.search((customer_id, "facts"))
    long_term_facts = [item.value for item in items]

    profile = get_db()[CUSTOMER_PROFILE_COLLECTION].find_one(
        {"customer_id": customer_id}, {"_id": 0}
    )

    return {
        "long_term_facts": long_term_facts,
        "customer_profile": profile or {},
    }


def make_reasoning(all_tools: list):
    """
    Fábrica que cria o nó reasoning com todas as tools disponíveis vinculadas ao LLM.
    all_tools deve incluir vector_search_clausulas + tools MCP de oficinas.
    """
    bound_llm = llm.bind_tools(all_tools) if all_tools else llm

    def reasoning(state: AgentState) -> dict:
        messages = state.get("messages", [])
        system_content = _build_system_context(state)
        llm_messages = [SystemMessage(content=system_content)] + messages

        response = bound_llm.invoke(llm_messages)

        # Se o LLM emitiu tool call(s), retorna sem extrair fato:
        # a resposta final (e extração de fato) virá numa próxima iteração do loop.
        if response.tool_calls:
            return {"messages": [response], "new_fact_to_save": None}

        # Resposta final (sem tool calls): extrai fato se houver.
        last_human = next(
            (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
        )
        new_fact = _extract_fact(last_human, response.content)
        return {"messages": [response], "new_fact_to_save": new_fact}

    return reasoning


def save_memory(state: AgentState, store: BaseStore) -> dict:
    """Nó fixo — executa sempre ao final do turno."""
    fact = state.get("new_fact_to_save")
    if not fact:
        return {}

    customer_id = state["customer_id"]
    key = fact.get("_key", "fact")
    clean_fact = {k: v for k, v in fact.items() if k != "_key"}

    store.put((customer_id, "facts"), key, clean_fact)
    return {}
