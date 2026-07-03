# Documentação Técnica — ClaraSeg

Este documento descreve cada componente técnico da implementação, as decisões de design tomadas e o raciocínio por trás delas. É destinado a servir de referência para explicar a arquitetura durante a apresentação.

---

## 1. Visão geral da arquitetura

```
┌───────────────────────────────────────────────────────────────────────┐
│                     webapp/ (React 19 + Vite SPA)                     │
│  ClientSidebar ── ChatPanel ── DebugPanel ── ClientProfileDialog      │
│  (Zustand store: src/store/uiStore.ts)                                │
└───────────┬───────────────────────────────────────┬───────────────────┘
            │ GET /clients, /clients/:id             │ GET /health
            │                                         │ POST /chat
            ▼                                         │ POST /chat/stream (SSE)
┌────────────────────────┐              ┌─────────────▼─────────────────┐
│  customer-api/          │              │  ai-agent/src/api.py           │
│  Node.js + Express      │              │  FastAPI                       │
│  (somente leitura)      │              └─────────────┬───────────────────┘
└───────────┬─────────────┘                            │ invoke() / astream()
            │                                           ▼
            │                          ┌─────────────────────────────────┐
            │                          │        ai-agent/src/agent.py     │
            │                          │  (async internamente;            │
            │                          │   asyncio.run() só em invoke())  │
            │                          └─────────────┬─────────────────────┘
            │                                        │
            │                            ┌───────────┴────────────┐
            │                            │  MultiServerMCPClient   │
            │                            │  (transporte HTTP)      │
            │                            └───────────┬────────────┘
            │                          ┌──────────────┼──────────────┐
            │                          ▼                              ▼
            │              ┌────────────────────┐      ┌────────────────────┐
            │              │  workshop-mcp/      │      │  policy-mcp/        │
            │              │  FastMCP :8000       │      │  FastMCP :8001       │
            │              │  (oficinas/agendas)   │      │  (gestão de apólices)│
            │              └───────────┬──────────┘      └───────────┬──────────┘
            │                          │                              │
┌───────────▼──────────────────────────▼──────────────────────────────▼──────────┐
│                              LangGraph StateGraph (ai-agent/src/graph/)          │
│                                                                                   │
│  START → load_memory → reasoning ⇄ tools_node → save_memory → END               │
│                            │ [tools_condition]                                  │
└──────────┬─────────────────────────────────┬────────────────────────────────────┘
           │                                 │
           ▼                                 ▼
┌────────────────────┐          ┌──────────────────────────────────────┐
│    MongoDB Atlas     │          │              OpenAI API                │
│                      │          │                                        │
│  short_term_memory   │          │  gpt-4o-mini (reasoning: decide chamar  │
│  (checkpointer)      │          │  tools ou responder; extrai fatos na    │
│                      │          │  resposta final)                        │
│  long_term_memory    │          │                                        │
│  (store)             │          │  text-embedding-3-small                │
│                      │          │  (embeddings de cláusulas + consultas)  │
│  policy_chunks       │          └──────────────────────────────────────┘
│  (vector search)     │
│                      │
│  customer_profile    │
│  workshops           │
└──────────────────────┘
```

Dois pontos de acoplamento intencionais e mínimos, um em cada direção do webapp:

- **Chat e transparência** — o webapp fala HTTP/SSE apenas com `ai-agent/src/api.py`, que por sua vez é um wrapper fino sobre `src.agent.invoke()` / `src.agent.astream()`. Toda a complexidade de grafo, memória, vector search e MCP fica encapsulada atrás dessas duas funções.
- **Sidebar e perfil do cliente** — dados somente-leitura de `customer_profile` (lista de clientes, modal de perfil) não passam pelo agente: são servidos por `customer-api`, um backend Node/Express separado que lê a mesma coleção diretamente via pymongo/driver Mongo do Node, sem qualquer conhecimento do grafo, tools ou memória.

O webapp nunca importa `ai-agent/src` nem conecta ao MongoDB diretamente — só HTTP contra esses dois backends.

---

## 2. LangGraph — orquestração do agente

### O que é o LangGraph

LangGraph é um framework para construir agentes com fluxo de execução explícito e controlado. Ele combina dois paradigmas: **nós fixos** (sempre executam, em todo turno) e **loop de tool-calling** (executam sob demanda, quando o LLM decide chamar uma ferramenta).

**Por que isso importa para a demo:** o fluxo é auditável e explicável. Os nós fixos (`load_memory`, `save_memory`) garantem que memória e persistência nunca são puladas, independente do conteúdo da pergunta. O loop de tool-calling deixa o LLM decidir quando buscar cláusulas, consultar oficinas ou mexer em apólices — sem acionar essas ferramentas desnecessariamente em perguntas simples.

### O StateGraph

Definido em `ai-agent/src/graph/build.py`. Um `StateGraph` é um grafo direcionado onde:
- Cada **nó** é uma função `(state) -> dict` que retorna as chaves do estado que deseja atualizar
- Cada **aresta** define a ordem de execução
- O **estado** é um `TypedDict` compartilhado entre todos os nós

```python
# ai-agent/src/graph/build.py
builder = StateGraph(AgentState)
builder.add_node("load_memory", load_memory)
builder.add_node("reasoning", reasoning_node)
builder.add_node("tools_node", ToolNode(all_tools))
builder.add_node("save_memory", save_memory)

builder.add_edge(START, "load_memory")
builder.add_edge("load_memory", "reasoning")
builder.add_conditional_edges(
    "reasoning", tools_condition, {"tools": "tools_node", END: "save_memory"}
)
builder.add_edge("tools_node", "reasoning")  # fecha o loop
builder.add_edge("save_memory", END)

return builder.compile(checkpointer=checkpointer, store=store)
```

O roteamento condicional usa `tools_condition`, um helper *prebuilt* do LangGraph: ele olha o último `AIMessage` e roteia para `"tools"` se houver `tool_calls` pendentes, ou para `END` caso contrário — remapeado aqui para `"save_memory"` em vez de terminar o grafo diretamente, já que ainda precisamos persistir o fato extraído.

A compilação (`compile`) é onde o checkpointer e o store são injetados. A partir daí, toda invocação do grafo automaticamente persiste e recupera estado do MongoDB.

### O AgentState

Definido em `ai-agent/src/graph/state.py`:

```python
class AgentState(TypedDict):
    customer_id: str
    messages: Annotated[list[BaseMessage], add_messages]  # histórico completo, incl. ToolMessages
    long_term_facts: list[dict]   # fatos persistentes sobre o cliente
    customer_profile: dict | None # apólices e sinistros (carregado por load_memory)
    new_fact_to_save: dict | None # canal entre reasoning e save_memory
```

Cada campo tem uma responsabilidade clara:
- `messages` é a "fita" completa da conversa: `HumanMessage`, `AIMessage` e `ToolMessage` (resultados de ferramentas). O reducer `add_messages` faz o merge automático a cada retorno de nó; o checkpointer persiste e restaura este campo automaticamente.
- Resultados de tool calls (cláusulas, oficinas, agenda, apólices) **não têm campo próprio no estado** — entram em `messages` como `ToolMessage`, o que dá ao LLM visibilidade imediata no histórico sem duplicar informação.
- `customer_profile` e `long_term_facts` são contexto fixo carregado por `load_memory` a cada turno e usado no system prompt do `reasoning`.
- `new_fact_to_save` é um canal de comunicação entre `reasoning` e `save_memory` — se não houver fato novo, é `None` e `save_memory` não escreve nada.

### Princípio arquitetural: nós fixos vs. tools condicionais

Dois tipos de elemento compõem o grafo:

- **Nós fixos** (`load_memory`, `save_memory`): executam em todo turno, incondicionalmente. Representam garantias estruturais — memória e persistência nunca dependem do conteúdo da mensagem.
- **Tools condicionais** (`vector_search_clausulas` + as tools MCP de oficinas e apólices): só executam quando o LLM decide chamá-las. Uma pergunta sobre o número da apólice não aciona busca semântica; uma pergunta sobre cobertura de colisão aciona.

Essa separação é o que permite ao agente ser ao mesmo tempo previsível (sempre carrega memória) e eficiente (não faz buscas ou chamadas de sistemas externos desnecessárias).

---

## 3. Memória de curto prazo — MongoDBSaver (checkpointer)

### O que é

O `MongoDBSaver` (pacote `langgraph-checkpoint-mongodb`) persiste o **estado completo do grafo** após cada nó ser executado. Isso inclui o campo `messages` com todo o histórico da conversa.

**A chave de identificação é o `thread_id`.** Toda vez que o grafo é invocado com o mesmo `thread_id`, o LangGraph:
1. Busca o checkpoint mais recente daquele thread no MongoDB
2. Restaura o estado a partir desse checkpoint (incluindo `messages`)
3. Executa os nós com o estado restaurado
4. Persiste o novo checkpoint ao final

Isso significa que **o histórico de conversa não é passado pela aplicação** — ele é recuperado automaticamente do banco antes de cada turno. O webapp mantém uma cópia local por cliente em `uiStore.conversations[customerId]` (Zustand) apenas para renderização imediata dos tokens à medida que chegam via SSE.

### Configuração

```python
# ai-agent/src/memory/checkpointer.py
def get_checkpointer() -> MongoDBSaver:
    client = MongoClient(MONGODB_URI)
    return MongoDBSaver(client, MONGODB_DB_NAME, "short_term_memory", "checkpoint_writes")
```

As coleções `short_term_memory` (checkpoints) e `checkpoint_writes` (writes intermediários por passo) são criadas automaticamente. O schema dos documentos é gerenciado internamente pelo LangGraph — não há necessidade de definir índices manualmente.

### Convenção de thread_id

```
thread_id = "{customer_id}_{uuid_hex[:8]}"
# exemplo: "cust_1001_a3f9b2c1"
```

O prefixo `customer_id` permite rastrear a qual cliente pertence cada sessão, mesmo que o checkpointer não exponha essa informação diretamente. O UUID garante unicidade entre sessões do mesmo cliente. `thread_id` é gerado por `api.py` (`_new_thread_id`) quando o webapp não envia um existente, e ecoado de volta no primeiro evento SSE (`{"type": "start", "thread_id": ...}`) para que o cliente HTTP possa persisti-lo e reutilizá-lo nas mensagens seguintes da mesma sessão.

### O que demonstra na apresentação

Dentro do mesmo `thread_id`, o agente lembra o que foi dito nas mensagens anteriores sem que a aplicação precise reenviar o histórico. Clicar em "Nova sessão" no `ChatPanel` (que chama `startNewSession` no store, gerando um `thread_id` novo na próxima mensagem) zera essa memória — o agente começa do zero, como se nunca tivesse falado com o cliente.

---

## 4. Memória de longo prazo — MongoDBStore

### O que é

O `MongoDBStore` (pacote `langgraph-store-mongodb`) é um armazenamento de chave-valor hierárquico para **fatos persistentes** sobre entidades (neste caso, clientes). Ao contrário do checkpointer, o store **não está vinculado a um thread_id** — o dado persiste independentemente de qual sessão está ativa.

```python
# ai-agent/src/memory/store.py
def get_store() -> MongoDBStore:
    client = MongoClient(MONGODB_URI)
    collection = client[MONGODB_DB_NAME]["long_term_memory"]
    return MongoDBStore(collection=collection)
```

### Estrutura de namespace

O store usa uma tupla como namespace:

```python
store.put((customer_id, "facts"), key, value)
store.search((customer_id, "facts"))
```

O namespace `(customer_id, "facts")` agrupa todos os fatos conhecidos sobre um cliente específico. A `key` permite sobrescrever um fato existente quando ele é atualizado (ex: segunda troca de carro usa a mesma chave e substitui o fato anterior).

### O que é salvo vs. o que não é

O nó `reasoning` faz **duas chamadas ao LLM** quando produz uma resposta final (sem tool calls pendentes): uma para gerar a resposta ao cliente, e uma segunda chamada específica (`_extract_fact`, sem a tag de streaming — ver seção 8) para classificar se a última mensagem do usuário contém um fato novo e duradouro.

```
Fatos duradouros (SALVAR): mudança de veículo, mudança de endereço,
                            preferência de contato, reclamação recorrente

Não são fatos duradouros (NÃO SALVAR): perguntas sobre cobertura, status de
                                        sinistro, saudações, agendamento de
                                        perícia, pedido de atualização de apólice
```

A segunda chamada ao LLM retorna JSON estruturado:
```json
{"has_fact": true, "key": "vehicle_change", "fact": "Cliente trocou para Compass 2025"}
```

Isso permite que o nó `save_memory` tome uma decisão binária — se `has_fact` for `false`, nada é escrito no banco.

### O que demonstra na apresentação

Clicar em "Nova sessão" zera a memória de curto prazo (`thread_id` novo). Mas ao perguntar algo que depende de um fato mencionado em uma sessão anterior, o agente ainda sabe — porque o fato foi persistido no `MongoDBStore`, que é independente do thread. Isso pode ser demonstrado dentro do próprio `DebugPanel`: a aba "Ações do agente" mostra o painel de fatos de longo prazo (`LongTermFactsPanel`) antes e depois de cada turno.

Este é o momento mais impactante da demo: mostrar que as duas camadas de memória são independentes e complementares.

---

## 5. Vector Search e ingestão de PDFs

### O que é vector search

Vector search é uma técnica de busca que encontra documentos semanticamente similares a uma consulta, sem depender de correspondência de palavras-chave. O texto da consulta e os textos do banco são convertidos em vetores de números (embeddings) por um modelo de linguagem. A busca retorna os documentos cujos vetores têm maior similaridade de cosseno com o vetor da consulta.

**O que torna isso poderoso:** a pergunta "o que acontece se eu bater o carro?" encontra a cláusula "Cobertura de colisão — veículos próprios" mesmo que nenhuma palavra da pergunta apareça literalmente no texto da cláusula. A similaridade é semântica, não lexical.

### Ingestão: PDFs reais via Docling (`data/ingestion/ingest.py`)

Diferente de um seed estático, as cláusulas de apólice vêm de PDFs reais processados por uma pipeline dedicada, separada de `data/seed.py`:

```
data/source_docs/
    auto/apolice_auto.pdf
    residencial/apolice_residencial.pdf
    vida/apolice_vida.pdf
```

O nome da subpasta vira a `category` do chunk. O fluxo:

1. **Extração estrutural com Docling** (`DocumentConverter`) — reconhece layout, títulos e tabelas do PDF; OCR é desabilitado explicitamente (`do_ocr=False`) porque as apólices têm texto nativo, não são digitalizadas.
2. **Chunking estrutural com `HybridChunker`** — respeita seções e tabelas (não corta no meio), usando um `OpenAITokenizer` real (via `tiktoken.encoding_for_model`) em vez de um tokenizer HuggingFace, para que o limite de tokens (`max_tokens=512` por padrão) reflita fielmente o modelo de embedding que será usado depois. `merge_peers=True` funde chunks pequenos adjacentes da mesma seção.
3. **Filtragem de chunks órfãos** — o Docling às vezes gera um chunk contendo só um rótulo de seção (ex: "Cláusula 5.1") sem corpo de texto, ou um chunk de sumário/índice sem conteúdo substantivo. Chunks com menos de `MIN_CHUNK_CHARS` (200 caracteres) são descartados antes mesmo de gerar embedding — economiza uma chamada de API para algo que nunca vai responder nada.
4. **Embeddings** — `text-embedding-3-small` via `OpenAIEmbeddings`, em lotes (`batch_size=64` por padrão).
5. **Upsert idempotente no Mongo** — o `_id` de cada chunk é `sha256(nome_do_arquivo + texto_do_chunk)` (`chunk_hash`), então rodar a ingestão de novo sobre os mesmos PDFs não duplica nada; só grava o que mudou.

Cada documento gravado na coleção `policy_chunks` tem essa forma:

```python
{
    "_id": "<sha256>",
    "text": "...",       # chunk contextualizado (headings injetados via chunker.contextualize())
    "embedding": [...],  # 1536 floats
    "metadata": {
        "source_file": "apolice_auto.pdf",
        "category": "auto",
        "section": "5.1 Cobertura de colisão",
        "headings": [...],
        "pages": [4, 5],
        "chunk_index": 3,
        "ingested_at": "...",
        "embedding_model": "text-embedding-3-small",
        "extraction_method": "docling",
    },
}
```

A primeira execução do Docling baixa modelos de layout (alguns GB) — deve ser feita com antecedência, antes de uma demo ao vivo.

### Geração de embeddings em tempo de consulta

```python
# ai-agent/src/embeddings.py
def embed(text: str) -> list[float]:
    response = _client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding
```

A cada turno da conversa, o embedding da mensagem do usuário é gerado em tempo real, e então a busca `$vectorSearch` compara esse vetor contra todos os embeddings armazenados em `policy_chunks`.

### A pipeline de aggregation em tempo de consulta

```python
# ai-agent/src/tools/vector_search.py
MIN_CHUNK_CHARS = 200  # segunda linha de defesa — o mesmo filtro da ingestão

pipeline = [
    {
        "$vectorSearch": {
            "index": VECTOR_INDEX_NAME,
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": 50,
            "limit": top_k * 4,             # margem para o $match seguinte descartar candidatos
            "filter": {"metadata.category": {"$eq": category}},  # só se category foi informado
        }
    },
    {"$match": {"$expr": {"$gte": [{"$strLenCP": "$text"}, MIN_CHUNK_CHARS]}}},
    {"$limit": top_k},
    {"$project": {
        "_id": 0, "score": {"$meta": "vectorSearchScore"},
        "text": 1, "category": "$metadata.category",
        "section": "$metadata.section", "source_file": "$metadata.source_file",
        "pages": "$metadata.pages",
    }},
]
```

O parâmetro `numCandidates` define quantos vizinhos aproximados o índice ANN (Approximate Nearest Neighbor) considera antes de aplicar filtros e retornar o `limit` final. `limit` no estágio `$vectorSearch` pede `top_k * 4` candidatos (não apenas `top_k`) porque o `$match` seguinte pode descartar alguns por tamanho — o `$match` é uma segunda linha de defesa contra chunks órfãos que, por algum motivo, passaram pelo filtro da ingestão (`MIN_CHUNK_CHARS` é a mesma constante nos dois lugares, aplicada em dois pontos diferentes do pipeline).

### Filtro por categoria (pre-filtering)

A tool `vector_search_clausulas` aceita um parâmetro `category` opcional (`"auto"`, `"residencial"` ou `"vida"`) que o próprio LLM decide passar, inferindo do perfil do cliente injetado no system prompt (campo `policies`). Isso demonstra **pre-filtering** combinado com vector search — uma feature específica do Atlas Vector Search que a maioria dos bancos de vetores standalone não suporta nativamente de forma eficiente. Um cliente só-auto não recebe cláusulas residenciais ou de vida mesmo que elas sejam semanticamente próximas da pergunta.

### O índice (criação manual necessária)

O índice de vector search precisa ser criado na Atlas UI porque a criação programática via driver pymongo não é suportada para índices de search. O índice define:
- Qual campo contém os vetores (`embedding`)
- A dimensionalidade (1536, deve bater com `text-embedding-3-small`)
- A métrica de similaridade (`cosine`)
- Quais campos podem ser usados como filtros (`metadata.category`)
- Deve ser criado na coleção `policy_chunks`, com o nome configurado em `VECTOR_INDEX_NAME` (`.env`)

---

## 6. Os nós e as tools do grafo

### Nó 1: `load_memory`

**Responsabilidade:** preparar todo o contexto não-conversacional antes do raciocínio. Faz duas operações independentes:

```python
# ai-agent/src/graph/nodes.py
def load_memory(state: AgentState, store: BaseStore) -> dict:
    items = store.search((state["customer_id"], "facts"))
    long_term_facts = [item.value for item in items]

    profile = get_db()[CUSTOMER_PROFILE_COLLECTION].find_one(
        {"customer_id": state["customer_id"]}, {"_id": 0}
    )
    return {"long_term_facts": long_term_facts, "customer_profile": profile or {}}
```

A distinção entre os dois é importante: o `MongoDBStore` é gerenciado pelo LangGraph e armazena fatos aprendidos em conversas. O `customer_profile` é dado operacional lido diretamente via pymongo — a mesma coleção que `customer-api` lê para a sidebar do webapp, e que `policy-mcp` escreve quando cria/atualiza apólices.

### As tools disponíveis ao LLM

Todas vivem sob o mesmo `ToolNode` (ver seção 9 para as MCP). Só `vector_search_clausulas` é local:

**`vector_search_clausulas`** (`ai-agent/src/tools/vector_search.py`) — LangChain `@tool`, não é um nó do grafo. A **docstring** é lida pelo LLM para decidir quando e como chamá-la — instrui "use quando o cliente relatar acidente/sinistro/furto/roubo ou perguntar sobre coberturas, exclusões, franquia, prazos... NÃO use para perguntas sobre dados do perfil". Ajustar a docstring é um ponto de controle direto sobre o comportamento da tool, tanto quanto o system prompt.

As demais seis tools (oficinas/agendamento) vêm de `workshop-mcp` e três (gestão de apólices) vêm de `policy-mcp` — ver seção 9.

### Nó 2: `reasoning` (com loop de tool-calling)

**Responsabilidade:** é o único nó de raciocínio. Pode ser chamado múltiplas vezes por turno via o loop `reasoning ⇄ tools_node`. É construído por uma fábrica (`make_reasoning`), não uma função solta, porque a lista de tools (que inclui as tools MCP buscadas dinamicamente) só existe depois que `agent.py` conecta ao `MultiServerMCPClient`:

```python
def make_reasoning(all_tools: list):
    bound_llm = llm.bind_tools(all_tools).with_config(tags=[ANSWER_LLM_TAG])

    def reasoning(state: AgentState) -> dict:
        system_content = _build_system_context(state)   # perfil + fatos LT injetados no prompt
        response = bound_llm.invoke([SystemMessage(content=system_content)] + state["messages"])

        if response.tool_calls:
            return {"messages": [response], "new_fact_to_save": None}

        # resposta final: extrai fato antes de fechar o turno
        last_human = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
        new_fact = _extract_fact(last_human, response.content)
        return {"messages": [response], "new_fact_to_save": new_fact}

    return reasoning
```

Toma uma de duas decisões a cada chamada:
- **Emite tool call(s):** retorna `AIMessage(tool_calls=[...])`. `tools_condition` roteia para `tools_node`, que executa e volta para `reasoning`.
- **Resposta final (sem tool calls):** retorna `AIMessage(content="...")` e, na mesma passagem, dispara a segunda chamada de extração de fato. `tools_condition` roteia para `save_memory`.

Isso permite **cadeias de tool calls** dentro do mesmo turno: o LLM pode chamar `vector_search_clausulas`, ver o resultado, decidir chamar `buscar_oficinas_proximas`, ver o resultado, e então gerar a resposta final — tudo sem nova mensagem do cliente. O system prompt (`SYSTEM_PROMPT` em `nodes.py`) é o que instrui esse encadeamento em detalhe: estrutura obrigatória de resposta em sinistros (acolhimento → sinistro relacionado no perfil → resposta técnica via tool → oferta de próximo passo), fluxo de confirmação explícita antes de `agendar_pericia`/`criar_apolice`/`atualizar_apolice`, e a regra de nunca reaproveitar resultado de tool de um turno anterior — cada mensagem nova reavalia do zero se alguma tool deve ser chamada de novo, mesmo que seja uma reformulação de algo já perguntado.

### Nó 3: `tools_node` (ToolNode unificado)

```python
all_tools = [vector_search_clausulas] + mcp_tools  # mcp_tools = workshop + policy, via MultiServerMCPClient
tool_node = ToolNode(all_tools)
```

Do ponto de vista do grafo, `vector_search_clausulas` (função Python local) e as dez tools MCP remotas (seis de `workshop-mcp`, três de `policy-mcp`) são tratadas exatamente da mesma forma — o `ToolNode` despacha para qualquer uma pelo nome, e o resultado vira `ToolMessage` em `messages`. O grafo não tem noção de "tool local" vs. "tool remota".

### Nó 4: `save_memory`

**Responsabilidade:** persistir o fato novo no `MongoDBStore`, se houver.

```python
def save_memory(state: AgentState, store: BaseStore) -> dict:
    fact = state.get("new_fact_to_save")
    if not fact:
        return {}
    key = fact.get("_key", "fact")
    clean_fact = {k: v for k, v in fact.items() if k != "_key"}
    store.put((state["customer_id"], "facts"), key, clean_fact)
    return {}
```

A lógica é mínima: se `new_fact_to_save` é `None`, nenhuma escrita acontece. A persistência do histórico de mensagens já é feita automaticamente pelo checkpointer — este nó só cuida dos fatos de longo prazo.

---

## 7. O ponto de entrada assíncrono — `agent.py`

```python
def invoke(thread_id: str, customer_id: str, message: str) -> dict: ...
async def astream(thread_id: str, customer_id: str, message: str): ...
```

`invoke()` é o contrato síncrono; `astream()` é seu equivalente em streaming, usado pelo endpoint SSE de `api.py`. Ambos retornam/produzem o mesmo formato final:

```python
{
    "response": "Texto da resposta da Clara",
    "debug": {
        "long_term_facts": [...],       # fatos recuperados do MongoDBStore
        "new_fact_saved": {...},        # fato gravado nesta interação, ou None
        "tool_calls_made": [            # tools chamadas neste turno, em ordem
            {"tool_name": "vector_search_clausulas", "input": {"query": "...", "category": "auto"},
             "output": [{"section": "...", "text": "...", "score": 0.91}]},
            {"tool_name": "buscar_oficinas_proximas", "input": {"cep": "04538-133", "tipo_servico": "colisao"},
             "output": [{"nome": "Auto Center Vivaz...", "distancia_km": 2.3}]},
        ],
    },
}
```

`tool_calls_made` é extraído das `messages` retornadas pelo grafo — `_extract_turn_tool_calls()` percorre as mensagens do turno atual (a partir de `_turn_messages_since`, que localiza a última `HumanMessage` igual à mensagem enviada) e casa cada `tool_calls[i]` de um `AIMessage` com o `ToolMessage` correspondente pelo `tool_call_id`. `_extract_turn_response_text()` concatena o conteúdo de **todas** as `AIMessage` do turno, não só a última — o modelo pode narrar (ex: "Poxa, sinto muito pelo acidente...") antes de emitir uma tool call, e essa narração intermediária não deve ser descartada da resposta final.

### Por que `agent.py` é async internamente

A integração MCP via `MultiServerMCPClient` usa `async with`/`await` para buscar as tools remotas por HTTP. Para usar isso dentro do LangGraph (`graph.ainvoke()` / `graph.astream_events()`), toda a cadeia precisa ser async:

```python
async def _build_graph_with_tools():
    checkpointer, store = _get_connections()
    mcp = MultiServerMCPClient(MCP_SERVER_CONFIG)   # {"oficinas": {...}, "apolices": {...}}
    mcp_tools = await mcp.get_tools()
    all_tools = [vector_search_clausulas] + mcp_tools
    return build_graph(checkpointer, store, all_tools)

async def _invoke_async(thread_id, customer_id, message) -> dict:
    graph = await _build_graph_with_tools()
    result = await graph.ainvoke(_build_input_state(customer_id, message),
                                  config={"configurable": {"thread_id": thread_id}})
    return _finalize(result, message)

def invoke(thread_id, customer_id, message) -> dict:
    return asyncio.run(_invoke_async(thread_id, customer_id, message))
```

`invoke()` é a única função pública síncrona — usa `asyncio.run()` como fronteira, para que `api.py`'s `POST /chat` (um `def` síncrono do FastAPI) possa chamá-la diretamente. `astream()` já assume que o chamador está em contexto async (o handler `POST /chat/stream` é `async def`), então não tem esse wrapper.

**Trade-off do ciclo de vida do cliente MCP:** o `MultiServerMCPClient` é recriado e a lista de tools é buscada de novo (`get_tools()`) a cada invocação, e o grafo é recompilado a cada chamada. Isso é intencionalmente simples — a compilação é barata (só construção de objetos Python) e uma requisição HTTP para listar tools é rápida comparada à latência do LLM. Manter um client/grafo global entre requisições evitaria esse overhead, mas exigiria gerenciar reconexão em caso de falha do MCP server — complexidade sem ganho perceptível para o ritmo de uma demo.

**Nota sobre o `ainvoke`/`astream_events` do grafo:** a cada chamada, o estado passado para o grafo contém só `customer_id` e a nova `HumanMessage`; os demais campos começam vazios e são preenchidos pelos nós. O histórico de `messages` é **restaurado pelo checkpointer** a partir do MongoDB antes de qualquer nó rodar, e o reducer `add_messages` faz o merge com a nova mensagem.

---

## 8. A API HTTP do agente — `api.py`

`ai-agent/src/api.py` é um segundo chamador, mais fino, do mesmo módulo `agent.py` — não tem lógica própria de grafo/memória/tools. Expõe três rotas via FastAPI:

| Rota | Método | Descrição |
|---|---|---|
| `/health` | GET | Faz `get_db().command("ping")`; retorna 503 se o Mongo estiver inacessível — a dependência crítica de toda invocação do agente. |
| `/chat` | POST | Chamada não-streaming: gera/reaproveita `thread_id`, chama `invoke()`, retorna `{"thread_id": ..., "response": ..., "debug": {...}}`. |
| `/chat/stream` | POST | SSE: emite `{"type": "start", "thread_id": ...}`, depois eventos de `astream()`. |

### Streaming token a token via `astream_events`

`astream()` filtra `graph.astream_events()` por um evento específico e uma tag específica:

```python
# ai-agent/src/graph/nodes.py
ANSWER_LLM_TAG = "clara_answer"
bound_llm = llm.bind_tools(all_tools).with_config(tags=[ANSWER_LLM_TAG])
```

```python
# ai-agent/src/agent.py
async for event in graph.astream_events(_build_input_state(customer_id, message), config=config):
    if event["event"] != "on_chat_model_stream":
        continue
    if ANSWER_LLM_TAG not in event.get("tags", []):
        continue
    yield {"type": "token", "content": event["data"]["chunk"].content}
```

A tag existe porque o nó `reasoning` faz **duas** chamadas ao LLM na mesma passagem (a resposta ao cliente e, em seguida, a extração de fato de longo prazo — seção 4). Sem a tag, os tokens das duas chamadas seriam indistinguíveis no stream de eventos, e o cliente HTTP acabaria vendo o JSON de `{"has_fact": ...}` vazando como se fosse parte da resposta. Só a chamada de resposta é tagueada; a de extração de fato roda com o LLM base, sem tag, e portanto nunca é streamada — só aparece no evento final.

Ao final do stream, `astream()` lê o estado final do grafo (`graph.aget_state(config)`) e emite um único evento `{"type": "done", "response": ..., "debug": {...}}`, no mesmo formato de `invoke()`. Se qualquer exceção ocorrer durante a construção do grafo ou a execução (ex: MCP server fora do ar), ela é capturada e vira `{"type": "error", "detail": str(e)}` em vez de derrubar a conexão SSE — por isso o `_build_graph_with_tools()` está *dentro* do `try`, diferente de `_invoke_async`.

### CORS e deploy

`CORS_ALLOWED_ORIGINS` (`.env`, default `http://localhost:5173`) controla quais origens podem chamar a API — necessário porque o webapp roda em porta/host diferente. Em produção containerizada, `ai-agent/Dockerfile` usa uma imagem `python:3.12-slim` com só `src/` copiado e roda `uvicorn src.api:app --host 0.0.0.0 --port 8080`; o `requirements.txt` do serviço deliberadamente **não inclui `docling`** (só usado pela ingestão, offline) para manter a imagem de serving enxuta. No `docker-compose.yml`, o serviço `ai-agent` sobrescreve `WORKSHOP_MCP_URL`/`POLICY_MCP_URL` para os nomes dos serviços vizinhos (`http://workshop-mcp:8000/mcp`, `http://policy-mcp:8001/mcp`) porque `localhost` não resolve entre containers diferentes.

---

## 9. Integração MCP — dois servidores de sistemas parceiros

### O que é o MCP (Model Context Protocol)

MCP é um protocolo aberto criado pela Anthropic para padronizar a forma como agentes de IA se conectam a sistemas externos. Em vez de cada integração ter sua própria API, o MCP define um contrato uniforme de "tools" que qualquer agente compatível pode descobrir e invocar.

**Por que usar MCP aqui, e não uma função Python direta?** A demo poderia simplesmente importar as funções dos servidores e chamá-las diretamente. Mas isso não demonstra o ponto arquitetural mais importante: em produção, tanto a rede de oficinas parceiras quanto o sistema de emissão de apólices pertencem a sistemas de terceiros — fora do codebase, fora da governança direta da seguradora. O MCP simula esse desacoplamento real: o agente conhece apenas o **contrato** da tool (nome, parâmetros, descrição), nunca a implementação.

### Transporte: HTTP (streamable-http), não stdio

Os dois servidores rodam como **processos/containers de longa duração**, não subprocessos spawnados por requisição. `ai-agent/src/tools/mcp_client.py` configura o `MultiServerMCPClient` para falar HTTP com cada um:

```python
# ai-agent/src/tools/mcp_client.py
MCP_SERVER_CONFIG = {
    "oficinas": {"url": WORKSHOP_MCP_URL, "transport": "http"},
    "apolices": {"url": POLICY_MCP_URL, "transport": "http"},
}
```

Cada servidor é implementado com `FastMCP` (`mcp.run(transport="streamable-http")`) e é **autocontido de propósito**: não importa nada de `ai-agent/src`, tem seu próprio `requirements.txt` mínimo e lê a conexão MongoDB direto de variáveis de ambiente — para poder ser buildado como imagem Docker independente, simulando um sistema de parceiro real acessado pela rede.

### `workshop-mcp/workshop_server.py` (porta 8000) — seis tools

Opera na coleção `workshops`, onde cada documento embute seu próprio array `appointments`.

| Tool | O que faz |
|---|---|
| `buscar_oficinas_proximas(cep, tipo_servico)` | Até 3 oficinas do mock que atendem o serviço pedido, ordenadas por distância (gerada aleatoriamente para simular variação real — o CEP é só metadado). |
| `consultar_agenda_pericia(oficina_id, urgencia)` | 3 slots de horário disponíveis; `urgencia="urgente"` começa a contar a partir de 1 dia, `"normal"` a partir de 2. |
| `agendar_pericia(cliente_id, oficina_id, data, horario, tipo_servico, urgencia)` | Confirma um agendamento. Um cliente só pode ter um agendamento `"confirmado"` por vez — se já existir, retorna `{"sucesso": false, "erro": "cliente_ja_possui_agendamento_aberto", "agendamento_existente": {...}}` em vez de criar um novo. |
| `listar_agendamentos_cliente(cliente_id)` | Todos os agendamentos do cliente (confirmados e cancelados), em qualquer oficina. |
| `cancelar_agendamento(cliente_id, agendamento_id)` | Marca o agendamento como `"cancelado"` (não remove o documento). |
| `alterar_agendamento(cliente_id, agendamento_id, nova_data, novo_horario)` | Atualiza data/horário de um agendamento existente. |

### `policy-mcp/policy_server.py` (porta 8001) — três tools

Opera diretamente na coleção `customer_profile` — a mesma que `load_memory` lê e que `customer-api` expõe para o webapp — onde cada cliente embute seu array `policies`.

| Tool | O que faz |
|---|---|
| `listar_apolices_cliente(cliente_id)` | Lista as apólices do cliente. Raramente necessária: as apólices já vêm injetadas no perfil do system prompt; a tool serve para confirmar estado atualizado antes de uma escrita. |
| `criar_apolice(cliente_id, tipo, vehicle?, address?)` | Cria uma apólice nova (`tipo="auto"` requer `vehicle`, `"residencial"` requer `address`). `status` nasce sempre `"pending"` e `renewal_date` é sempre calculado como hoje + 1 ano — nunca informado pelo chamador. |
| `atualizar_apolice(cliente_id, apolice_id, vehicle?, address?)` | Atualiza o campo correspondente ao tipo da apólice; qualquer atualização força `status` de volta para `"pending"` e renova `renewal_date`. Rejeita `vehicle` em apólice residencial e vice-versa. |

### O fluxo pró-ativo de gestão de apólices

Diferente das tools de oficina (reativas — só disparam quando o cliente pede), o system prompt instrui o LLM a **oferecer** proativamente a criação/atualização de apólice sempre que o cliente mencionar, em qualquer ponto da conversa, a troca/compra de um veículo ou uma mudança de endereço — mesmo que o cliente não tenha perguntado sobre apólices. O fluxo definido no prompt:

1. Responder à necessidade imediata do cliente primeiro, então perguntar se ele quer criar uma nova apólice ou atualizar uma existente (consultando `policies` do perfil para contextualizar a pergunta).
2. Coletar apenas os dados que ainda faltam — nunca repetir uma pergunta sobre algo já informado na conversa ou já presente no perfil/fatos duradouros.
3. Montar um resumo e pedir confirmação explícita ("Está correto?") antes de chamar `criar_apolice`/`atualizar_apolice` — nunca antes da confirmação, mesmo que os dados pareçam completos.
4. Informar o `policy_id` retornado e deixar claro que a apólice fica com status pendente até revisão humana.

### O que demonstra na apresentação

Esse é o momento em que o agente deixa de ser puramente consultivo e passa a **agir sobre sistemas externos** — dois deles, cada um representando um domínio de negócio diferente (parceiros de reparo vs. emissão de apólices), ambos acessados pelo mesmo protocolo uniforme. Vale contrastar explicitamente:
- Antes: agente consulta memória e cláusulas (dados passivos)
- Agora: agente invoca uma ferramenta de um sistema parceiro via protocolo padronizado — e no caso de apólices, faz isso proativamente, sem que o cliente precise saber pedir

Abrir a aba "Ações do agente" no `DebugPanel` depois de uma pergunta de oficina ou apólice mostra o `ToolCallCard` com os dados brutos que vieram do servidor MCP antes da composição da resposta final; a aba "Logs brutos" mostra o JSON completo do último `debug` retornado pela API.

---

## 10. `customer-api` — leitura de perfis de cliente

`customer-api/` é um backend Node.js/Express/TypeScript standalone, cujo único propósito é servir dados de `customer_profile` somente-leitura para a sidebar e o modal de perfil do webapp — **sem** passar pelo agente, pelo grafo ou por qualquer camada de memória.

```typescript
// customer-api/src/server.ts
app.get("/clients", async (_req, res) => { ... });              // lista resumida (sidebar)
app.get("/clients/:customerId", async (req, res) => { ... });   // perfil completo (modal)
```

- `GET /clients` retorna uma projeção resumida (nome, tipos de apólice, preferência de contato, contagem de sinistros `"em_analise"`) — nunca o array completo de `claims`/`policies`, para manter o payload leve na sidebar.
- `GET /clients/:customerId` retorna o documento completo (exceto `_id`) — o mesmo schema que `load_memory` lê no agente.

Reutiliza as credenciais Mongo do `.env` da raiz do repo (`customer-api/src/db.ts` carrega primeiro `customer-api/.env`, depois o `.env` raiz — `dotenv.config()` nunca sobrescreve uma var já definida, então a segunda chamada só preenche o que faltar). Roda na porta `8090`, com CORS restrito a `CORS_ALLOWED_ORIGINS` como o `ai-agent`.

**Por que uma API separada, e não uma rota a mais em `ai-agent/src/api.py`?** Porque a listagem de clientes é uma leitura simples e barata, e não deveria depender de nenhuma das dependências pesadas do agente (LangGraph, MCP, OpenAI). O acoplamento mínimo aqui — `customer-api` conhece só `customer_profile`, nada de grafo/memória/tools — é o mesmo princípio de design do resto do sistema: cada serviço só sabe o que precisa saber.

---

## 11. A interface React (webapp)

### Separação de responsabilidades

O webapp é uma SPA React 19 + Vite + TypeScript + Tailwind, com estado global centralizado em um único store Zustand (`webapp/src/store/uiStore.ts`):

| Componente | Responsabilidade |
|---|---|
| `ClientSidebar` | Lista de clientes (via `customer-api`), seleção do cliente ativo |
| `ChatPanel` | Renderização das mensagens, input, botão "Nova sessão" |
| `DebugPanel` | Abas "Ações do agente" (fatos de longo prazo + tool calls) e "Logs brutos" (JSON cru do último turno) |
| `ClientProfileDialog` | Modal com o perfil completo do cliente (via `customer-api`) |

`App.tsx` apenas monta os quatro lado a lado; toda a lógica de estado e chamadas de rede vive no store e em `webapp/src/lib/` (`api.ts`, `sse.ts`).

### Por que uma conversa por cliente, e não uma conversa global

`uiStore.conversations` é um `Record<customerId, ClientConversation>` — cada cliente selecionado na sidebar tem seu próprio histórico local, `thread_id` e último `debug`, todos mantidos em memória do navegador. Trocar de cliente na sidebar não descarta a conversa anterior; ela continua lá (com seu `thread_id`) se o usuário voltar. Isso espelha, no lado do webapp, a mesma ideia de escopo por `thread_id` do backend.

### Consumo do streaming SSE

`webapp/src/lib/sse.ts` usa `@microsoft/fetch-event-source` em vez do `EventSource` nativo do browser, porque `EventSource` não suporta `POST` com corpo — e `/chat/stream` precisa receber `customer_id`/`message`/`thread_id` no body. `sendMessage` no store:

1. Insere otimisticamente a mensagem do usuário e uma mensagem do agente vazia (`pending: true`) no histórico.
2. A cada evento `{"type": "token", ...}`, concatena o `content` na mensagem pendente — é isso que dá o efeito de texto aparecendo token a token.
3. No evento `{"type": "done", ...}`, substitui o texto acumulado pelo `response` final (mais confiável que a concatenação incremental), marca a mensagem como não mais pendente, e grava `debug`/`toolCallHistory` para o `DebugPanel`.
4. No evento `{"type": "error", ...}` (ou numa falha de rede), remove a mensagem pendente e insere uma mensagem de sistema com o erro, em vez de deixar uma bolha vazia travada.

### O painel de debug como ferramenta de apresentação

O `DebugPanel` é o análogo direto do antigo `st.expander` da versão Streamlit, mas sempre visível (com botão de minimizar, não um accordion fechado por padrão). A aba "Ações do agente" mostra:
- `LongTermFactsPanel` — os fatos de longo prazo conhecidos sobre o cliente, e se um fato novo foi gravado nesta interação
- `ToolCallCard` por cada tool chamada no turno, com input e output brutos

A aba "Logs brutos" mostra o `debug` completo do último turno como JSON — útil para inspecionar scores de vector search ou payloads de erro do MCP sem precisar abrir o console do navegador.

### Deploy

`webapp/Dockerfile` é multi-stage: build com `node:20-slim` (`npm run build`), servido por `nginx:1.27-alpine`. As variáveis `VITE_API_BASE_URL`/`VITE_CUSTOMER_API_BASE_URL` são *baked* no bundle JS **em tempo de build** (Vite resolve `import.meta.env.VITE_*` estaticamente) — por isso, no `docker-compose.yml`, elas apontam para os hosts/portas publicados (`http://localhost:8080`, `http://localhost:8090`), não para os nomes de serviço internos do compose: quem resolve essas URLs é o navegador do usuário, fora da rede Docker.

---

## 12. Modelo de dados no MongoDB

### Cinco coleções, regimes de gestão distintos

| Coleção | Gerenciada por | Descrição |
|---|---|---|
| `short_term_memory` | LangGraph (`MongoDBSaver`) | Checkpoints da conversa por `thread_id`. Schema interno — não editar manualmente. |
| `long_term_memory` | LangGraph (`MongoDBStore`) | Fatos persistentes por `customer_id`. Schema interno — não editar manualmente. |
| `policy_chunks` | `data/ingestion/ingest.py` | Chunks de cláusulas + embeddings, gerados a partir de PDFs via Docling. Requer o índice de vector search manual (seção 5). |
| `customer_profile` | `data/seed.py` (seed inicial) + `policy-mcp` (escrita) + `customer-api`/`ai-agent` (leitura) | Perfis, apólices (`policies`) e sinistros (`claims`) dos clientes. É a única coleção escrita por mais de um serviço. |
| `workshops` | `data/seed.py` (seed inicial) + `workshop-mcp` (leitura/escrita de `appointments`) | Oficinas parceiras; cada documento embute seu próprio array `appointments`. |

As coleções gerenciadas pelo LangGraph têm schema interno — não devem ser editadas manualmente. As coleções gerenciadas pela aplicação têm schema explícito definido nos arquivos JSON de seed (`data/seed_customer_profiles.json`, `data/seed_workshops.json`, ambos gitignored e fornecidos localmente) ou gerado pela pipeline de ingestão.

### Por que embeddings ficam no mesmo documento que o texto

Cada documento de `policy_chunks` armazena o texto do chunk e seu embedding no mesmo documento. Isso tem uma consequência importante: o pipeline de `$vectorSearch` pode retornar o texto (e os metadados de seção/página) junto com o score de similaridade em uma única operação de aggregation, sem necessidade de um segundo lookup por `_id`. Para uma coleção de algumas dezenas a centenas de chunks, o tamanho do campo `embedding` (1536 floats × 8 bytes ≈ 12KB por documento) é completamente negligenciável.

---

## 13. Decisões de design e trade-offs

| Decisão | Escolha feita | Trade-off |
|---|---|---|
| Orquestração do agente | LangGraph com fluxo explícito | Mais verboso que agente ReAct, mas previsível e auditável |
| Nós sequenciais vs. paralelos | Sequencial | Mais simples de explicar; em produção, paralelizar `load_memory` + o primeiro tool call reduziria latência |
| Extração de fatos | Segunda chamada ao LLM com JSON, na mesma passagem do nó `reasoning` | +1 round-trip por turno que produz resposta final, mas mais simples que function calling formal dedicado |
| Retorno de `invoke()`/`astream()` | `dict`/eventos com `response` + `debug` | Acoplamento mínimo com a UI; o mesmo formato serve chamadas síncronas e o evento final do streaming |
| Streaming de tokens | Filtro de `astream_events()` por tag (`ANSWER_LLM_TAG`) | Precisa marcar explicitamente a chamada de resposta para não vazar tokens da extração de fato; alternativa (duas chamadas LLM completamente separadas em nós diferentes) tornaria o grafo mais complexo |
| Embeddings | `text-embedding-3-small` (OpenAI) | Consistente com o LLM já usado; Voyage AI seria opção com melhor custo/qualidade para produção |
| Ingestão de cláusulas | PDFs reais via Docling + `HybridChunker`, upsert idempotente por hash | Mais fiel a um cenário real que um seed estático de texto; primeira execução exige baixar modelos de layout (GBs) |
| Filtragem por categoria | LLM decide passar `category` com base no perfil injetado no prompt | Demonstra pre-filtering nativo do Atlas sem lógica extra no grafo; depende do LLM inferir corretamente a partir do perfil |
| Transporte MCP | HTTP (`streamable-http`), servidores como processos/containers de longa duração | Precisa gerenciar disponibilidade de rede dos MCP servers (surfaced como evento `error` no SSE); em troca, simula fielmente um sistema de parceiro real acessado pela rede, e permite dois servidores independentes rodando em paralelo |
| Número de servidores MCP | Dois (`workshop-mcp`, `policy-mcp`), cada um autocontido e sem import de `ai-agent/src` | Mais containers para orquestrar do que um único servidor "genérico"; em troca, cada domínio de negócio (oficinas vs. apólices) fica isolado como um sistema de terceiro independente, mais próximo do cenário real |
| Ciclo de vida do cliente MCP | `MultiServerMCPClient` recriado e grafo recompilado a cada invocação | Uma chamada HTTP extra de `get_tools()` por turno; evita gerenciar reconexão/estado global entre requisições |
| Sidebar/perfil de cliente | API Node/Express dedicada (`customer-api`), sem passar pelo agente | Um serviço a mais para rodar, mas remove qualquer dependência de LangGraph/MCP/OpenAI de uma leitura simples e frequente |
| Frontend | React SPA (Vite) + Zustand, servido via Nginx em produção | Mais peças móveis que uma UI Streamlit de página única, mas permite streaming token a token de verdade, estado por cliente, e uma separação limpa de UI/API |
| Histórico local na UI | `uiStore.conversations` (Zustand) como cache por cliente | Evita re-fetch a cada re-render; aceita risco de divergência do estado "oficial" no Mongo (improvável durante a demo, já que a UI é o único cliente) |
