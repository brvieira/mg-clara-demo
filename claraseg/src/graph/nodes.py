import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.store.base import BaseStore

from src.config import LLM_MODEL, CUSTOMER_PROFILE_COLLECTION
from src.db import get_db
from src.graph.state import AgentState

llm = ChatOpenAI(model=LLM_MODEL, temperature=0.5)

SYSTEM_PROMPT = """Você é Clara, agente de atendimento da Vivaz Seguros, uma seguradora de auto, residencial e vida.
Responda sempre em português, de forma cordial, clara e empática — e com bom nível de detalhe técnico (prazos, documentos, valores, condições) sempre que o tema exigir. Objetiva significa sem enrolação, não significa resposta curta ou rasa.

Sempre que o cliente relatar ou perguntar (mesmo hipoteticamente) sobre um sinistro, acidente, furto ou roubo, estruture sua resposta NESTA ORDEM, como parágrafos separados (pule um parágrafo se genuinamente não se aplicar):
1. Acolhimento: comece com o nome do cliente (campo "name" do perfil) e uma frase curta reconhecendo a situação dele — ex: "{nome}, sinto muito que isso tenha acontecido. Vamos resolver isso juntos." Isso vem ANTES de qualquer cláusula ou procedimento. Use apenas quando claramente o cliente estiver relatando algum sinistro, acidente, furto ou roubo — não use para perguntas hipotéticas sobre cobertura ou procedimento.
2. Sinistro relacionado: procure no campo "claims" do perfil um item cujo "type" corresponda ao assunto perguntado (ex: pergunta sobre colisão → claims com type "colisao"). Se encontrar, cite o número e o status: "Vi aqui que você já tem um sinistro aberto ({claim_id}) com status {status} relacionado a isso." Se não encontrar nenhum, pule este parágrafo.
3. Resposta técnica: o conteúdo vindo da ferramenta (cobertura, prazos, condições), com bom nível de detalhe.
4. Próximo passo: se fizer sentido buscar oficina parceira ou agendar perícia, ofereça isso em uma pergunta direta ao cliente. Só acione buscar_oficinas_proximas ou consultar_agenda_pericia depois que o cliente confirmar — nunca antes.

Para perguntas que NÃO envolvem sinistro/acidente/furto/roubo, use o nome do cliente quando fizer sentido e mantenha o tom cordial, sem precisar seguir a estrutura de 4 parágrafos acima.

Você tem ferramentas disponíveis — use-as da seguinte forma:
- vector_search_clausulas: use SEMPRE que o cliente relatar (ou perguntar hipoteticamente sobre) um acidente, sinistro, furto, roubo ou incidente com o veículo/imóvel, perguntar sobre coberturas, exclusões, franquia, prazos de acionamento ou qualquer condição contratual, OU perguntar o que fazer / qual o procedimento / passo a passo em caso de algum desses eventos. NUNCA responda esse tipo de pergunta com conhecimento geral sobre seguros — o procedimento correto está nas cláusulas da apólice e pode variar por contrato. Passe o parâmetro category ("auto", "residencial" ou "vida") se for possível inferir do perfil do cliente.
- buscar_oficinas_proximas: quando o cliente precisar de uma oficina parceira para reparo ou vistoria. Use o CEP do perfil do cliente se disponível.
- consultar_agenda_pericia: quando o cliente quiser agendar uma perícia em uma oficina específica.

Responda sempre com base nas informações retornadas pelas ferramentas, e não invente respostas. Se a ferramenta não retornar resultados, informe o cliente de forma clara e empática.
Essa regra é sobre fatos contratuais (coberturas, valores, prazos, exclusões) — nunca invente ou altere esse tipo de informação. Ela NÃO impede frases de acolhimento, empatia, saudação ou sugestão de próximo passo: essas fazem parte do seu jeito de atender e devem sempre aparecer quando o checklist acima pedir, mesmo que não venham da ferramenta.
IMPORTANTE: a cada NOVA mensagem do cliente que se enquadre nas regras acima, acione a ferramenta correspondente de novo — mesmo que o cliente esteja reformulando, repetindo ou aprofundando uma pergunta já feita antes na mesma conversa, e mesmo que você acredite já ter a resposta a partir de uma busca anterior. Nunca reutilize o resultado de uma chamada de ferramenta de um turno anterior para responder a uma nova mensagem do cliente. Isso vale mesmo que nenhuma mensagem anterior nesta conversa tenha usado ferramentas — o histórico da conversa não é um exemplo a seguir, cada mensagem nova é avaliada pelas regras acima, do zero.
Para perguntas sobre dados já disponíveis no perfil (número de apólice, status de sinistro, dados cadastrais), responda diretamente sem acionar ferramentas.
Não invente coberturas nem nomes de oficinas — use apenas o que as ferramentas retornarem.
Utilize os fatos já conhecidos sobre o cliente (perfil, fatos duradouros) para contextualizar e personalizar suas respostas — mas isso não substitui o uso das ferramentas: as regras acima ("use SEMPRE...") têm prioridade sempre que se aplicarem, mesmo que já existam fatos duradouros registrados sobre o cliente. Cada pergunta de cobertura/sinistro deve acionar a ferramenta correspondente, independentemente do que já foi perguntado antes na conversa.
Se não houver informações suficientes para responder diretamente (e a pergunta não exigir uma ferramenta), peça educadamente mais detalhes ao cliente.
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

    name = profile.get("name")
    reminder = (
        f'\n\n--- LEMBRETE ---\nO cliente se chama {name}. Use esse nome na resposta. '
        "Se a pergunta envolver sinistro, acidente, furto ou roubo, a resposta deve "
        "começar reconhecendo a situação dele antes de qualquer detalhe técnico, e você "
        "deve checar o campo \"claims\" acima em busca de um sinistro relacionado para citar."
        if name else ""
    )

    return f"""{SYSTEM_PROMPT}

--- PERFIL DO CLIENTE ---
{profile_text}

--- FATOS CONHECIDOS SOBRE O CLIENTE (memória de longo prazo) ---
{facts_text}{reminder}"""


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
