# SPEC.md — Agente ClaraSeg (Backend)

## 1. Visão geral

ClaraSeg é um agente de atendimento ao cliente para uma seguradora de auto/residencial fictícia. O agente responde perguntas sobre cobertura de apólice, status de sinistro e dados de cadastro, usando memória de curto prazo (contexto da conversa atual) e memória de longo prazo (fatos persistentes sobre o cliente entre conversas diferentes), além de busca semântica nas cláusulas do contrato via MongoDB Atlas Vector Search.

## 2. Stack técnica

- **Linguagem:** Python 3.11+
- **Orquestração de agente:** LangGraph (`langgraph`)
- **Memória de curto prazo:** `langgraph-checkpoint-mongodb` (classe `MongoDBSaver`)
- **Memória de longo prazo:** `langgraph-store-mongodb` (classe `MongoDBStore`)
- **Banco de dados:** MongoDB Atlas (cluster M0 ou superior, região mais próxima)
- **LLM:** OpenAI (`gpt-4o-mini` ou equivalente — definir via variável de ambiente para poder trocar facilmente)
- **Embeddings:** OpenAI (`text-embedding-3-small`) ou Voyage AI (`voyage-3`) — decidir na implementação; ambos compatíveis com Atlas Vector Search
- **Driver MongoDB:** `pymongo`
- **Gerenciamento de variáveis de ambiente:** `python-dotenv`

## 3. Estrutura de diretórios proposta

```
claraseg/
├── .env.example
├── requirements.txt
├── SPEC.md
├── data/
│   ├── seed_policy_clauses.json
│   └── seed_customer_profiles.json
├── mcp_servers/
│   └── workshop_server.py      # MCP server standalone, processo separado, transporte stdio
├── src/
│   ├── __init__.py
│   ├── config.py              # carrega variáveis de ambiente, configs de conexão
│   ├── db.py                  # cliente MongoDB, helpers de conexão
│   ├── seed.py                # script para popular as 4 coleções com dados de exemplo
│   ├── embeddings.py          # geração de embeddings para vector search
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── checkpointer.py    # configuração do MongoDBSaver (curto prazo)
│   │   └── store.py           # configuração do MongoDBStore (longo prazo)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── vector_search.py   # tool de busca semântica em policy_clauses (chamada condicional pelo LLM)
│   │   └── mcp_client.py       # cliente MCP — conecta o LangGraph ao workshop_server
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py           # definição do AgentState (TypedDict)
│   │   ├── nodes.py           # implementação de load_memory, reasoning, save_memory
│   │   └── build.py           # construção e compilação do StateGraph, incluindo tools_node
│   └── agent.py                # ponto de entrada: invoke(thread_id, customer_id, message) -> resposta
└── tests/
    └── test_agent_smoke.py     # teste manual de fluxo ponta a ponta (não unitário formal)
```

## 4. Modelo de dados (MongoDB Atlas)

### 4.1 Coleção `short_term_memory`

Gerenciada automaticamente pelo `MongoDBSaver` do LangGraph — **não desenhar schema manualmente**, apenas configurar a conexão. Armazena o checkpoint da conversa por `thread_id`. Cada thread_id representa uma sessão/conversa.

Convenção de `thread_id`: `"{customer_id}_{session_uuid}"` — permite rastrear qual cliente pertence a qual sessão, mesmo que o checkpointer não exponha isso diretamente.

### 4.2 Coleção `long_term_memory`

Gerenciada pelo `MongoDBStore` do LangGraph. Estrutura de namespace hierárquico:

```
namespace: (customer_id, "facts")
key: identificador do fato (ex: "vehicle_change", "preferred_contact_method")
value: {
  "fact": "Cliente trocou de veículo em 2026, novo carro é um Compass 2025",
  "recorded_at": "2026-06-20T14:30:00Z",
  "source_thread_id": "cust_1001_a3f9..."
}
```

Regra de negócio para gravação: o nó `save_memory` só grava um novo fato de longo prazo quando o LLM identificar explicitamente uma informação nova e duradoura sobre o cliente (mudança de veículo, mudança de endereço, preferência de contato, reclamação recorrente). Não gravar a conversa inteira como fato — isso é responsabilidade do checkpointer.

### 4.3 Coleção `policy_clauses`

Schema por documento:

```json
{
  "_id": "ObjectId",
  "clause_id": "auto_cobertura_colisao_01",
  "category": "auto | residencial | sinistro_geral",
  "title": "Cobertura de colisão — veículos próprios",
  "text": "Texto completo da cláusula em português, linguagem de contrato real.",
  "embedding": [0.0123, -0.0456, ...],
  "embedding_model": "text-embedding-3-small",
  "updated_at": "2026-01-15T00:00:00Z"
}
```

**Índice de Vector Search** (criar via Atlas UI ou API, nome sugerido `policy_clauses_vector_index`):

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "category"
    }
  ]
}
```

O filtro por `category` permite restringir a busca semântica (ex: só buscar em cláusulas de "auto" se o cliente tem apenas apólice de carro) — usar isso na demo para mostrar domínio de filtros combinados com vector search, não só busca pura.

Dataset mínimo: 8-10 cláusulas cobrindo: cobertura de colisão, cobertura de terceiros, assistência 24h, carro reserva, cobertura de incêndio residencial, cobertura de roubo, franquia, prazo de acionamento de sinistro, exclusões de cobertura, portabilidade de bônus.

### 4.4 Coleção `customer_profile`

Schema por documento:

```json
{
  "_id": "ObjectId",
  "customer_id": "cust_1001",
  "name": "Nome fictício",
  "policies": [
    {
      "policy_id": "POL-AUTO-9981",
      "type": "auto",
      "vehicle": "Honda Civic 2022",
      "status": "active",
      "renewal_date": "2026-11-01"
    }
  ],
  "claims": [
    {
      "claim_id": "CLM-4471",
      "type": "colisao",
      "status": "em_analise",
      "opened_at": "2026-06-10",
      "description": "Colisão traseira em estacionamento"
    }
  ],
  "contact_preference": "whatsapp"
}
```

Dataset mínimo: 2-3 clientes fictícios com perfis distintos (um só com apólice de auto, um com auto + residencial, um com sinistro aberto) para permitir variedade no discovery ao vivo.

## 5. Definição do grafo (LangGraph)

### 5.0 Princípio arquitetural

Dois tipos de nó compõem o grafo, com responsabilidades distintas:

- **Nós fixos** — sempre executam, independente do conteúdo da mensagem. Representam garantias estruturais da conversa, não decisões de conteúdo. Nesta arquitetura: `load_memory` e `save_memory`.
- **Tools condicionais** — só executam se o LLM, durante o `reasoning`, decidir que precisa delas para responder à mensagem atual. Nesta arquitetura: `vector_search_clausulas` (busca semântica em cláusulas) e as tools do MCP de oficinas/peritos (seção 10).

`load_memory` é fixo porque garante contexto e sequência da conversa — é uma propriedade estrutural do agente, não uma decisão que dependa da pergunta do cliente. Tratá-lo como tool abriria a possibilidade do LLM "esquecer" de carregar memória em algum turno, comprometendo a premissa central da demo (memória confiável entre sessões). Já a busca de cláusulas e a consulta a oficinas só fazem sentido para um subconjunto das perguntas possíveis — perguntar "qual o número da minha apólice?" não deveria disparar busca vetorial nem consulta a oficinas, por exemplo.

### 5.1 Estado do agente (`AgentState`)

```python
class AgentState(TypedDict):
    customer_id: str
    messages: list[BaseMessage]       # histórico da conversa atual, incluindo ToolMessages de qualquer tool call
    long_term_facts: list[dict]        # fatos recuperados do MongoDBStore para este customer_id
    new_fact_to_save: dict | None      # se o reasoning identificar um fato novo, populado aqui
```

Nota: não há mais um campo `retrieved_clauses` ou `workshop_results` separado no estado. O resultado de qualquer tool call (vector search ou MCP) entra no histórico de `messages` como um `ToolMessage`, seguindo o padrão nativo do LangGraph — isso mantém o LLM com visibilidade total do que foi recuperado, no mesmo lugar onde ele vê o restante da conversa, e evita duplicar a mesma informação em dois lugares do estado.

### 5.2 Nós e tools

**`load_memory`** (nó fixo — sempre executa, em todo turno, antes do `reasoning`)

- Lê o customer_id do estado.
- Busca no `MongoDBStore`, namespace `(customer_id, "facts")`, todos os fatos conhecidos.
- Busca o perfil estruturado em `customer_profile` (apólices, sinistros) — isso não é memória de agente, é dado operacional direto, buscar via `pymongo` comum.
- Popula `long_term_facts` no estado.

**`reasoning`** (nó fixo — orquestra as tools, mas não é ele mesmo uma tool)

- Recebe: histórico da conversa (via checkpointer), `long_term_facts`, perfil do cliente.
- Tem as tools vinculadas via `bind_tools`: `vector_search_clausulas`, `buscar_oficinas_proximas`, `consultar_agenda_pericia` (as duas últimas vêm do MCP, ver seção 10).
- O LLM decide, a cada chamada, se responde diretamente ou se emite uma ou mais tool calls.
- Se emitir tool call(s), o grafo roteia para `tools_node` e, ao retornar, chama `reasoning` novamente com o resultado da tool já no histórico — permitindo cadeias de tool calls (ex: buscar cobertura E checar oficina na mesma interação, em chamadas sucessivas).
- Se não emitir tool call, o conteúdo da resposta do LLM é a resposta final ao cliente.
- Adicionalmente, ao gerar a resposta final, identifica se a mensagem do usuário contém um fato novo e duradouro que deveria ser persistido (ex: "troquei de carro"). Se sim, popula `new_fact_to_save`.

**`tools_node`** (executor de tools — unifica vector search e MCP sob o mesmo mecanismo)

- Implementado com o `ToolNode` nativo do LangGraph, que já sabe invocar qualquer tool vinculada ao LLM e devolver o resultado como `ToolMessage` — não há lógica manual de despacho a escrever.
- Agrupa todas as tools disponíveis ao agente:
  - `vector_search_clausulas(query: str, category: str | None) -> list[dict]` — executa `$vectorSearch` na coleção `policy_clauses`, com filtro opcional de `category`. Implementação em `src/tools/vector_search.py` (ver 5.5).
  - `buscar_oficinas_proximas` e `consultar_agenda_pericia` — tools do MCP de oficinas/peritos, ver seção 10.
- O roteamento entre `reasoning` e `tools_node` usa o helper nativo `tools_condition` do LangGraph, que inspeciona a última mensagem do LLM e identifica automaticamente se há tool call pendente.

**`save_memory`** (nó fixo — sempre executa após `final_response`)

- O checkpointer (`MongoDBSaver`) já persiste o histórico de mensagens automaticamente a cada passo do grafo — comportamento padrão do LangGraph ao usar um checkpointer no momento da compilação.
- Se `new_fact_to_save` estiver populado, grava no `MongoDBStore` no namespace `(customer_id, "facts")`.

### 5.3 Fluxo do grafo

```
START → load_memory → reasoning → [tools_condition] → tools_node → reasoning (loop)
                                  → save_memory → END
```

O `tools_condition` é avaliado a cada retorno do `reasoning`: se a última mensagem do LLM contém tool call(s) pendente(s), o grafo vai para `tools_node`; caso contrário, segue direto para `save_memory`. Isso forma um loop entre `reasoning` e `tools_node` que se repete até o LLM decidir que tem informação suficiente para responder — podendo ser zero, uma, ou múltiplas iterações dependendo da complexidade da pergunta do cliente (ex: uma pergunta que precise tanto de cobertura quanto de oficina pode disparar duas tool calls em turnos sucessivos antes de chegar à resposta final).

`load_memory` só aparece uma vez por turno, sempre no início — ele não faz parte do loop de tools, por ser um nó fixo (ver 5.0).

### 5.4 Compilação do grafo

```python
graph = builder.compile(checkpointer=mongodb_saver, store=mongodb_store)
```

Isso é o que ativa as duas camadas de memória automaticamente para todas as invocações do grafo.

### 5.5 Implementação da tool `vector_search_clausulas`

Diferente de um nó de grafo com acesso direto ao estado, é uma função decorada como tool LangChain, com schema explícito de input para o LLM saber quando e como chamá-la:

```python
from langchain_core.tools import tool

@tool
def vector_search_clausulas(query: str, category: str | None = None) -> list[dict]:
    """
    Busca cláusulas de apólice relevantes por similaridade semântica.
    Use esta tool quando o cliente perguntar sobre cobertura, exclusões,
    franquia, ou qualquer condição contratual específica.

    Args:
        query: a pergunta ou tópico de cobertura mencionado pelo cliente.
        category: opcional — "auto", "residencial" ou "sinistro_geral",
                  se for possível inferir do contexto da conversa.
    """
    ...
```

A docstring é o que orienta o LLM sobre quando chamar a tool — vale revisar e ajustar essa descrição se, durante os testes, o agente chamar a tool com frequência maior ou menor do que o esperado.

## 6. Função de entrada (`agent.py`)

```python
def invoke(thread_id: str, customer_id: str, message: str) -> str:
    """
    thread_id: identifica a sessão/conversa atual (curto prazo)
    customer_id: identifica o cliente (usado para a memória de longo prazo e perfil)
    message: texto da mensagem do usuário

    Retorna a resposta em texto do agente.
    """
```

Esta função é o único ponto de integração que a interface Streamlit precisa conhecer. Toda a complexidade do grafo, memória e vector search fica encapsulada aqui.

## 7. Variáveis de ambiente (`.env.example`)

```
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
MONGODB_DB_NAME=claraseg
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
VECTOR_INDEX_NAME=policy_clauses_vector_index
```

## 8. Critérios de aceite (para validar antes da apresentação)

1. Duas conversas em `thread_id` diferentes, mesmo `customer_id`: o segundo thread consegue recuperar um fato mencionado no primeiro (prova de memória de longo prazo).
2. Dentro do mesmo `thread_id`, o agente lembra o que foi dito 2-3 mensagens atrás sem precisar repetir (prova de memória de curto prazo / checkpointer).
3. Pergunta em linguagem natural sobre cobertura retorna a cláusula correta (prova de vector search funcional) — testar com pelo menos 3 perguntas formuladas de forma diferente da redação literal da cláusula, para demonstrar que é busca semântica e não busca por palavra-chave.
4. Pergunta sobre status de sinistro retorna dado correto do `customer_profile` (prova de integração com dado operacional, não só memória de agente).
5. O agente não inventa cobertura que não existe nas cláusulas carregadas (mitigação básica de alucinação — vale mencionar na apresentação como ponto de atenção arquitetural, mesmo sem implementar guardrails formais).
6. Uma pergunta puramente factual sobre dado já carregado em `long_term_facts` ou `customer_profile` (ex: "qual o número da minha apólice?") deve ser respondida pelo `reasoning` **sem** disparar nenhuma tool call — confirma que o LLM não chama tools desnecessariamente.
7. Uma pergunta sobre cobertura deve disparar exatamente uma chamada a `vector_search_clausulas`, não múltiplas chamadas redundantes para a mesma pergunta.
8. Uma pergunta combinada (cobertura + oficina, ver exemplo na seção 10.5) deve disparar `vector_search_clausulas` e `buscar_oficinas_proximas` em sequência, dentro do mesmo turno de resposta, sem exigir uma nova mensagem do cliente entre uma chamada e outra.
9. `load_memory` deve aparecer nos logs/traces de execução em 100% dos turnos, independente do conteúdo da mensagem — confirma que esse nó nunca é pulado.

## 9. Fora de escopo (mencionar explicitamente se perguntado)

- Autenticação real de usuário (a demo usa seleção manual de `customer_id`).
- Function calling para ações (abrir sinistro, atualizar dados) — a demo é só consulta/leitura.
- Streaming de tokens da resposta do LLM (resposta é retornada completa).
- Avaliação automatizada de qualidade de resposta (RAGAS ou similar) — mencionar como próximo passo natural se perguntado sobre produção.
- Reranking dos resultados do vector search (Voyage rerank-2.5) — mencionar como otimização possível.

## 10. Integração com MCP — rede de oficinas e peritos parceiros

### 10.1 Visão geral

Esta seção estende o agente com uma nova capacidade de ação: ao identificar que o cliente precisa de assistência prática relacionada a um sinistro (vistoria, reparo), o agente consulta um servidor MCP externo que simula o sistema de uma rede de oficinas e peritos parceiros da seguradora — retornando oficinas próximas e horários de agenda disponíveis.

A motivação arquitetural é deliberada: em vez de implementar essa busca como uma função Python chamada diretamente, ela é exposta via protocolo MCP, simulando um cenário realista em que esse sistema pertence a um parceiro de negócio externo, fora do codebase e da governança direta da seguradora. Isso testa e demonstra desacoplamento real entre o agente e sistemas de terceiros — o agente conhece apenas o contrato da tool, nunca a implementação por trás dela.

### 10.2 Estrutura de diretórios

Já incorporada na estrutura geral do projeto (seção 3) — `mcp_servers/workshop_server.py` e `src/tools/mcp_client.py`. Não há nó de grafo dedicado a essa integração; as tools do MCP são consumidas pelo `tools_node` unificado (ver 10.5).

### 10.3 Mock MCP server (`mcp_servers/workshop_server.py`)

Implementado com o SDK oficial `mcp` (`fastmcp`), transporte `stdio` — adequado para demo local, sem necessidade de expor porta de rede.

**Tool 1 — `buscar_oficinas_proximas`**

| Campo                  | Tipo                                            | Descrição                                                                                           |
| ---------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `cep` (input)          | string                                          | CEP de referência do cliente                                                                        |
| `tipo_servico` (input) | enum: `colisao`, `vidro`, `pintura`, `mecanica` | Tipo de serviço necessário                                                                          |
| retorno                | list[dict]                                      | Até 3 oficinas, ordenadas por distância, com `oficina_id`, `nome`, `distancia_km`, `atende_servico` |

**Tool 2 — `consultar_agenda_pericia`**

| Campo                | Tipo                      | Descrição                                           |
| -------------------- | ------------------------- | --------------------------------------------------- |
| `oficina_id` (input) | string                    | Identificador retornado pela tool anterior          |
| `urgencia` (input)   | enum: `normal`, `urgente` | Define o intervalo mínimo de antecedência da agenda |
| retorno              | list[dict]                | 3 horários disponíveis, com `data` e `horario`      |

```python
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
import random

mcp = FastMCP("oficinas-parceiras")

OFICINAS_MOCK = [
    {"id": "of_001", "nome": "Auto Center Vivaz Zona Sul", "cep_base": "04", "servicos": ["colisao", "pintura", "mecanica"]},
    {"id": "of_002", "nome": "Oficina Rápida Centro", "cep_base": "01", "servicos": ["colisao", "vidro"]},
    {"id": "of_003", "nome": "Master Auto Glass", "cep_base": "05", "servicos": ["vidro", "pintura"]},
]

@mcp.tool()
def buscar_oficinas_proximas(cep: str, tipo_servico: str) -> list[dict]:
    """Busca oficinas parceiras próximas a um CEP que atendem o tipo de serviço solicitado."""
    candidatas = [o for o in OFICINAS_MOCK if tipo_servico in o["servicos"]]
    resultado = []
    for o in candidatas:
        distancia = round(random.uniform(1.5, 8.0), 1)
        resultado.append({
            "oficina_id": o["id"],
            "nome": o["nome"],
            "distancia_km": distancia,
            "atende_servico": tipo_servico,
        })
    return sorted(resultado, key=lambda x: x["distancia_km"])[:3]

@mcp.tool()
def consultar_agenda_pericia(oficina_id: str, urgencia: str) -> list[dict]:
    """Consulta os próximos horários disponíveis para perícia/vistoria em uma oficina."""
    hoje = datetime.now()
    intervalo = 1 if urgencia == "urgente" else 2
    horarios = []
    for i in range(3):
        data = hoje + timedelta(days=intervalo + i)
        horarios.append({
            "data": data.strftime("%Y-%m-%d"),
            "horario": random.choice(["09:00", "11:30", "14:00", "16:30"]),
        })
    return horarios

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 10.4 Integração com o grafo (`src/tools/mcp_client.py`)

Usar `langchain-mcp-adapters` para converter as tools MCP em tools LangChain compatíveis com `bind_tools`:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

mcp_client = MultiServerMCPClient({
    "oficinas": {
        "command": "python",
        "args": ["mcp_servers/workshop_server.py"],
        "transport": "stdio",
    }
})

workshop_tools = await mcp_client.get_tools()
```

### 10.5 Unificação com o `tools_node`

As tools do MCP **não têm nó próprio no grafo** — não existe um nó `find_workshop` separado. Em vez disso, elas são registradas no mesmo `tools_node` unificado descrito na seção 5.2, junto com `vector_search_clausulas`:

```python
all_tools = [vector_search_clausulas] + workshop_tools

llm_with_tools = llm.bind_tools(all_tools)
tools_node = ToolNode(all_tools)
```

Isso significa que o `reasoning` vê todas as tools disponíveis — busca de cláusulas e MCP de oficinas — no mesmo ponto de decisão, e o `tools_condition` nativo do LangGraph cuida do roteamento independentemente de qual(is) tool(s) o LLM decidiu chamar. Não há necessidade de lógica condicional manual distinguindo "tool de vector search" de "tool de MCP" — do ponto de vista do grafo, são todas apenas tools vinculadas ao mesmo `reasoning`.

Essa unificação é o que permite, por exemplo, uma pergunta como _"abri um sinistro de colisão, o que minha apólice cobre e qual oficina perto de mim consegue me atender?"_ disparar `vector_search_clausulas` e `buscar_oficinas_proximas` em turnos sucessivos dentro do mesmo loop `reasoning ⇄ tools_node`, sem exigir uma nova mensagem do cliente entre uma chamada e outra.

### 10.6 Estado — sem campo adicional

Não é necessário nenhum campo novo em `AgentState` para a integração com MCP. O resultado de `buscar_oficinas_proximas` e `consultar_agenda_pericia`, assim como o de `vector_search_clausulas`, entra no histórico de `messages` como `ToolMessage` — seguindo o mesmo mecanismo descrito na seção 5.1.

### 10.7 Nota de apresentação (não faz parte do código, mas do roteiro de demo)

Este componente é o ponto da demonstração onde o agente deixa de ser puramente consultivo (responder com base em memória e busca semântica) e passa a **agir sobre um sistema externo**, via um protocolo padronizado de integração. Vale destacar explicitamente esse contraste ao apresentar o diagrama de arquitetura — e mencionar que, do ponto de vista do grafo, essa ação e a busca semântica são tratadas pelo mesmo mecanismo de tool-calling (seção 10.5), o que simplifica a arquitetura sem perder a distinção conceitual entre "buscar informação interna" e "agir sobre um sistema de parceiro externo".
