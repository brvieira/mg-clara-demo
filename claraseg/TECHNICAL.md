# Documentação Técnica — ClaraSeg

Este documento descreve cada componente técnico da implementação, as decisões de design tomadas e o raciocínio por trás delas. É destinado a servir de referência para explicar a arquitetura durante a apresentação.

---

## 1. Visão geral da arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py (Streamlit)                   │
│  sidebar.py ── chat.py ── debug_panel.py                    │
└────────────────────────┬────────────────────────────────────┘
                         │ invoke(thread_id, customer_id, msg)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      src/agent.py                           │
│     (async internamente; asyncio.run() na borda pública)    │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │  async with MCP     │
              │  MultiServerClient  │── stdio ──► mcp_servers/
              └──────────┬──────────┘            workshop_server.py
                         │                       (subprocesso)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              LangGraph StateGraph (src/graph/)              │
│                                                             │
│  START → load_memory → reasoning ←──────────────────┐      │
│                            │                        │      │
│                     [tools_condition]          tools_node  │
│                            │ sem tools          (ToolNode) │
│                            ↓                        │      │
│                       save_memory              tool call   │
│                            │                        │      │
│                           END ────────────────────►─┘      │
└─────────┬───────────────────┬─────────────────────────────┘
          │                   │
          ▼                   ▼
┌──────────────────┐  ┌──────────────────────────────────────┐
│  MongoDB Atlas   │  │          OpenAI API                  │
│                  │  │                                      │
│  short_term_     │  │  gpt-4o-mini (reasoning: decide      │
│  memory          │  │  chamar tools ou responder; extrai   │
│  (checkpointer)  │  │  fatos na resposta final)            │
│                  │  │                                      │
│                  │  │  text-embedding-3-small              │
│  long_term_      │  │  (embeddings para vector search)    │
│  memory          │  └──────────────────────────────────────┘
│  (store)         │
│                  │
│  policy_clauses  │
│  (vector search) │
│                  │
│  customer_       │
│  profile         │
│  (dados          │
│  operacionais)   │
└──────────────────┘
```

O ponto de acoplamento entre a interface e o backend é intencional e mínimo: a UI só precisa conhecer a função `invoke()`. Toda a complexidade de grafo, memória, vector search e MCP fica encapsulada no backend.

---

## 2. LangGraph — orquestração do agente

### O que é o LangGraph

LangGraph é um framework para construir agentes com fluxo de execução explícito e controlado. Ele combina dois paradigmas: **nós fixos** (sempre executam, em todo turno) e **loop de tool-calling** (executam sob demanda, quando o LLM decide chamar uma ferramenta).

**Por que isso importa para a demo:** o fluxo é auditável e explicável. Os nós fixos (`load_memory`, `save_memory`) garantem que memória e persistência nunca são puladas, independente do conteúdo da pergunta. O loop de tool-calling deixa o LLM decidir quando buscar cláusulas ou consultar oficinas — sem acionar essas ferramentas desnecessariamente em perguntas simples.

### O StateGraph

Definido em `src/graph/build.py`. Um `StateGraph` é um grafo direcionado onde:
- Cada **nó** é uma função `(state) -> dict` que retorna as chaves do estado que deseja atualizar
- Cada **aresta** define a ordem de execução
- O **estado** é um `TypedDict` compartilhado entre todos os nós

```python
# src/graph/build.py
builder = StateGraph(AgentState)
builder.add_node("load_memory", load_memory)
# ...
return builder.compile(checkpointer=checkpointer, store=store)
```

A compilação (`compile`) é onde o checkpointer e o store são injetados. A partir daí, toda invocação do grafo automaticamente persiste e recupera estado do MongoDB.

### O AgentState

Definido em `src/graph/state.py`:

```python
class AgentState(TypedDict):
    customer_id: str
    messages: list[BaseMessage]   # histórico completo, incluindo ToolMessages de qualquer tool call
    long_term_facts: list[dict]   # fatos persistentes sobre o cliente
    customer_profile: dict | None # apólices e sinistros (carregado por load_memory)
    new_fact_to_save: dict | None # canal entre reasoning e save_memory
```

Cada campo tem uma responsabilidade clara:
- `messages` é a "fita" completa da conversa: `HumanMessage`, `AIMessage` e `ToolMessage` (resultados de ferramentas). O checkpointer persiste e restaura este campo automaticamente.
- Resultados de tool calls (cláusulas, oficinas, agenda) **não têm campo próprio no estado** — entram em `messages` como `ToolMessage`, o que dá ao LLM visibilidade imediata no histórico sem duplicar informação.
- `customer_profile` e `long_term_facts` são contexto fixo carregado por `load_memory` a cada turno e usado no system prompt do `reasoning`.
- `new_fact_to_save` é um canal de comunicação entre `reasoning` e `save_memory` — se não houver fato novo, é `None` e `save_memory` não escreve nada.

### Princípio arquitetural: nós fixos vs. tools condicionais

Dois tipos de elemento compõem o grafo:

- **Nós fixos** (`load_memory`, `save_memory`): executam em todo turno, incondicionalmente. Representam garantias estruturais — memória e persistência nunca dependem do conteúdo da mensagem.
- **Tools condicionais** (`vector_search_clausulas`, `buscar_oficinas_proximas`, `consultar_agenda_pericia`): só executam quando o LLM decide chamá-las. Uma pergunta sobre o número da apólice não aciona busca semântica; uma pergunta sobre cobertura de colisão aciona.

Essa separação é o que permite ao agente ser ao mesmo tempo previsível (sempre carrega memória) e eficiente (não faz buscas desnecessárias).

---

## 3. Memória de curto prazo — MongoDBSaver (checkpointer)

### O que é

O `MongoDBSaver` (pacote `langgraph-checkpoint-mongodb`) persiste o **estado completo do grafo** após cada nó ser executado. Isso inclui o campo `messages` com todo o histórico da conversa.

**A chave de identificação é o `thread_id`.** Toda vez que o grafo é invocado com o mesmo `thread_id`, o LangGraph:
1. Busca o checkpoint mais recente daquele thread no MongoDB
2. Restaura o estado a partir desse checkpoint (incluindo `messages`)
3. Executa os nós com o estado restaurado
4. Persiste o novo checkpoint ao final

Isso significa que **o histórico de conversa não é passado pela aplicação** — ele é recuperado automaticamente do banco antes de cada turno. A UI mantém uma cópia local em `session_state.chat_history` apenas para renderização rápida.

### Configuração

```python
# src/memory/checkpointer.py
MongoDBSaver.from_conn_string(
    MONGODB_URI,
    db_name=MONGODB_DB_NAME,
    collection_name="short_term_memory",
)
```

A coleção `short_term_memory` é criada automaticamente. O schema do documento é gerenciado internamente pelo LangGraph — não há necessidade de definir índices manualmente.

### Convenção de thread_id

```
thread_id = "{customer_id}_{uuid_hex[:8]}"
# exemplo: "cust_1001_a3f9b2c1"
```

O prefixo `customer_id` permite rastrear a qual cliente pertence cada sessão, mesmo que o checkpointer não exponha essa informação diretamente. O UUID garante unicidade entre sessões do mesmo cliente.

### O que demonstra na apresentação

Dentro do mesmo `thread_id`, o agente lembra o que foi dito nas mensagens anteriores sem que a aplicação precise reenviar o histórico. Ao clicar em "Nova conversa" (novo `thread_id`), essa memória é zerada — o agente começa do zero, como se nunca tivesse falado com o cliente.

---

## 4. Memória de longo prazo — MongoDBStore

### O que é

O `MongoDBStore` (pacote `langgraph-store-mongodb`) é um armazenamento de chave-valor hierárquico para **fatos persistentes** sobre entidades (neste caso, clientes). Ao contrário do checkpointer, o store **não está vinculado a um thread_id** — o dado persiste independentemente de qual sessão está ativa.

### Estrutura de namespace

O store usa uma tupla como namespace:

```python
store.put((customer_id, "facts"), key, value)
store.search((customer_id, "facts"))
```

O namespace `(customer_id, "facts")` agrupa todos os fatos conhecidos sobre um cliente específico. A `key` permite sobrescrever um fato existente quando ele é atualizado (ex: segunda troca de carro usa a mesma chave e substitui o fato anterior).

### O que é salvo vs. o que não é

O nó `reasoning` faz **duas chamadas ao LLM**: uma para gerar a resposta ao cliente, e uma segunda chamada específica para classificar se a mensagem do usuário contém um fato novo e duradouro.

```
Fatos duradouros (SALVAR): mudança de veículo, mudança de endereço,
                            preferência de contato, reclamação recorrente

Não são fatos duradouros (NÃO SALVAR): perguntas sobre cobertura,
                                        status de sinistro, saudações
```

A segunda chamada ao LLM retorna JSON estruturado:
```json
{"has_fact": true, "key": "vehicle_change", "fact": "Cliente trocou para Compass 2025"}
```

Isso permite que o nó `save_memory` tome uma decisão binária — se `has_fact` for `false`, nada é escrito no banco.

### O que demonstra na apresentação

Clicar em "Nova conversa" zera a memória de curto prazo (`thread_id` novo). Mas ao perguntar algo que depende de um fato mencionado em uma sessão anterior, o agente ainda sabe — porque o fato foi persistido no `MongoDBStore`, que é independente do thread.

Este é o momento mais impactante da demo: mostrar que as duas camadas de memória são independentes e complementares.

---

## 5. Vector Search — Atlas Vector Search

### O que é

Vector search é uma técnica de busca que encontra documentos semanticamente similares a uma consulta, sem depender de correspondência de palavras-chave. O texto da consulta e os textos do banco são convertidos em vetores de números (embeddings) por um modelo de linguagem. A busca retorna os documentos cujos vetores têm maior similaridade de cosseno com o vetor da consulta.

**O que torna isso poderoso:** a pergunta "o que acontece se eu bater o carro?" encontra a cláusula "Cobertura de colisão — veículos próprios" mesmo que nenhuma palavra da pergunta apareça literalmente no texto da cláusula. A similaridade é semântica, não lexical.

### Geração de embeddings

```python
# src/embeddings.py
response = _client.embeddings.create(input=text, model=EMBEDDING_MODEL)
return response.data[0].embedding  # lista de 1536 floats
```

O modelo `text-embedding-3-small` da OpenAI gera vetores de 1536 dimensões. Cada cláusula da apólice tem seu embedding gerado uma única vez, no momento do seed, e armazenado no campo `embedding` do documento MongoDB.

A cada turno da conversa, o embedding da mensagem do usuário é gerado em tempo real, e então a busca `$vectorSearch` compara esse vetor contra todos os embeddings armazenados.

### A pipeline de aggregation

```python
# src/tools/vector_search.py
pipeline = [
    {
        "$vectorSearch": {
            "index": VECTOR_INDEX_NAME,
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": 50,  # considera os 50 mais próximos antes de filtrar
            "limit": 3,           # retorna os 3 melhores
        }
    },
    {
        "$project": {
            "embedding": 0,   # exclui o vetor do retorno (economiza payload)
            "score": {"$meta": "vectorSearchScore"},  # expõe o score de similaridade
            "clause_id": 1, "category": 1, "title": 1, "text": 1,
        }
    },
]
```

O parâmetro `numCandidates` define quantos vizinhos aproximados o índice ANN (Approximate Nearest Neighbor) considera antes de aplicar filtros e retornar o `limit` final. Valor maior = mais preciso, mais lento.

### Filtro por categoria

```python
# src/graph/nodes.py — nó vector_search
policy_types = {p["type"] for p in profile.get("policies", [])}
if len(policy_types) == 1:
    category = policy_types.pop()  # "auto" ou "residencial"
```

Se o cliente tem apenas um tipo de apólice, o filtro é aplicado automaticamente:

```python
"filter": {"category": {"$eq": "auto"}}
```

Isso demonstra o uso de **pre-filtering** combinado com vector search — uma feature específica do Atlas Vector Search que a maioria dos bancos de vetores standalone não suporta nativamente de forma eficiente. Um cliente só-auto não recebe cláusulas residenciais mesmo que elas sejam semanticamente próximas da pergunta.

### O índice (criação manual necessária)

O índice de vector search precisa ser criado na Atlas UI porque a criação programática via driver pymongo não é suportada para índices de search. O índice define:
- Qual campo contém os vetores (`embedding`)
- A dimensionalidade (1536, deve bater com o modelo)
- A métrica de similaridade (`cosine`)
- Quais campos podem ser usados como filtros (`category`)

---

## 6. Os quatro nós do grafo

### Nó 1: `load_memory`

**Responsabilidade:** preparar todo o contexto não-conversacional antes do raciocínio.

Faz duas operações independentes:

1. **Busca no MongoDBStore** os fatos de longo prazo do cliente:
   ```python
   items = store.search((customer_id, "facts"))
   long_term_facts = [item.value for item in items]
   ```

2. **Busca direta via pymongo** o perfil estruturado do cliente (apólices, sinistros):
   ```python
   profile = get_db()[CUSTOMER_PROFILE_COLLECTION].find_one(
       {"customer_id": customer_id}, {"_id": 0}
   )
   ```

A distinção entre os dois é importante: o MongoDBStore é gerenciado pelo LangGraph e armazena fatos aprendidos em conversas. O `customer_profile` é dado operacional gerenciado diretamente pela aplicação, independente do agente.

### Tool: `vector_search_clausulas`

**Tipo:** LangChain `@tool` — não é um nó do grafo, é uma ferramenta disponível ao LLM.

Definida em `src/tools/vector_search.py`. Quando o LLM decide chamar esta tool, o `tools_node` (ToolNode) executa a função e adiciona o resultado ao histórico como `ToolMessage`. O LLM vê os resultados das cláusulas no mesmo contexto da conversa e decide se deve chamar mais tools ou gerar a resposta final.

A **docstring** da tool é lida pelo LLM para decidir quando e como chamá-la — é ela que instrui "use quando o cliente perguntar sobre cobertura, exclusões, franquia... NÃO use para perguntas sobre dados do perfil". Ajustar a docstring é o principal ponto de controle sobre o comportamento da tool.

O parâmetro `category` é passado pelo LLM com base no que ele infere do perfil do cliente no system prompt — o LLM decide filtrar por "auto", "residencial" ou deixar sem filtro.

### Nó 2: `reasoning` (com loop de tool-calling)

**Responsabilidade:** é o único nó de raciocínio. Pode ser chamado múltiplas vezes por turno via o loop `reasoning ⇄ tools_node`.

O LLM recebe:
- System prompt com perfil do cliente e fatos de longo prazo
- Histórico completo de `messages` (HumanMessages + AIMessages anteriores + ToolMessages de resultados de tools)

Toma uma de duas decisões:
- **Emite tool call(s):** retorna `AIMessage(tool_calls=[...])`. O `tools_condition` roteia para `tools_node`, que executa e volta para `reasoning`. 
- **Resposta final (sem tool calls):** retorna `AIMessage(content="...")`. Nesse ponto, faz uma segunda chamada ao LLM para extração de fato e popula `new_fact_to_save`. O `tools_condition` roteia para `save_memory`.

Isso permite **cadeias de tool calls** dentro do mesmo turno: o LLM pode chamar `vector_search_clausulas`, ver o resultado, decidir chamar `buscar_oficinas_proximas`, ver o resultado, e então gerar a resposta final — tudo sem nova mensagem do cliente.

### Nó 3: `tools_node` (ToolNode unificado)

**Implementado com `ToolNode(all_tools)` do LangGraph prebuilt, onde:**
```python
all_tools = [vector_search_clausulas] + mcp_tools
```

Do ponto de vista do grafo, `vector_search_clausulas` (função Python local) e as tools do MCP (`buscar_oficinas_proximas`, `consultar_agenda_pericia`, vindas do subprocesso via `MultiServerMCPClient`) são tratadas exatamente da mesma forma — o `ToolNode` despacha para qualquer uma pelo nome, e o resultado vira `ToolMessage` em `messages`.

### Nó 4: `save_memory`

**Responsabilidade:** persistir o fato novo no MongoDBStore, se houver.

```python
def save_memory(state: AgentState, store: BaseStore) -> dict:
    fact = state.get("new_fact_to_save")
    if not fact:
        return {}
    key = fact.get("_key", "fact")
    clean_fact = {k: v for k, v in fact.items() if k != "_key"}
    store.put((customer_id, "facts"), key, clean_fact)
    return {}
```

A lógica é mínima: se `new_fact_to_save` é `None`, nenhuma escrita acontece. A persistência do histórico de mensagens já é feita automaticamente pelo checkpointer — este nó só cuida dos fatos de longo prazo.

---

## 7. O ponto de entrada — `agent.py`

```python
def invoke(thread_id: str, customer_id: str, message: str) -> dict:
```

Esta função é o contrato entre a UI e o backend. Retorna:

```python
{
    "response": "Texto da resposta da Clara",
    "debug": {
        "long_term_facts": [...],       # fatos recuperados do MongoDBStore
        "new_fact_saved": {...},        # fato gravado nesta interação, ou None
        "tool_calls_made": [            # tools chamadas neste turno, em ordem
            {
                "tool_name": "vector_search_clausulas",
                "input": {"query": "...", "category": "auto"},
                "output": [{"title": "...", "text": "...", "score": 0.91}]
            },
            {
                "tool_name": "buscar_oficinas_proximas",
                "input": {"cep": "04538-133", "tipo_servico": "colisao"},
                "output": [{"nome": "Auto Center Vivaz...", "distancia_km": 2.3}]
            }
        ]
    }
}
```

`tool_calls_made` é extraído das `messages` retornadas pelo grafo — `_extract_turn_tool_calls()` percorre as mensagens após a última `HumanMessage` e coleta pares `(AIMessage.tool_calls[i], ToolMessage correspondente)`.

**Por que `agent.py` é async internamente:**

A integração MCP via `MultiServerMCPClient` usa `async with` para gerenciar o ciclo de vida do subprocesso. Para usar isso dentro do LangGraph (`graph.ainvoke()`), toda a cadeia precisa ser async. A função pública `invoke()` é síncrona (chamada pelo Streamlit), e usa `asyncio.run()` como fronteira:

```python
async def _invoke_async(...) -> dict:
    async with MultiServerMCPClient(MCP_SERVER_CONFIG) as mcp:
        mcp_tools = await mcp.get_tools()
        all_tools = [vector_search_clausulas] + mcp_tools
        graph = build_graph(checkpointer, store, all_tools)
        result = await graph.ainvoke(...)
    return {...}

def invoke(...) -> dict:
    return asyncio.run(_invoke_async(...))
```

**Trade-off de ciclo de vida do subprocesso MCP:**

O subprocesso é iniciado e encerrado a cada invocação (`async with`). Isso adiciona ~150ms por mensagem para iniciar o processo Python. A alternativa — manter o subprocesso vivo entre invocações — exigiria gerenciamento de ciclo de vida mais complexo (sem ganho perceptível para o ritmo de uma demo ao vivo). O grafo também é recompilado a cada chamada (necessário para injetar as tools MCP); a compilação é rápida (milissegundos, só criação de objetos Python).

**Nota sobre o `invoke` do grafo:** a cada chamada, o estado passado para o grafo contém `customer_id` e a nova mensagem. Os demais campos começam vazios — eles são preenchidos pelos nós. O histórico de `messages` é **restaurado pelo checkpointer** a partir do MongoDB, e então a nova `HumanMessage` é adicionada. O LangGraph faz o merge internamente.

---

## 8. A interface Streamlit

### Separação de responsabilidades

A UI está dividida em três módulos independentes:

| Arquivo | Responsabilidade |
|---|---|
| `ui/sidebar.py` | Seleção de cliente, controle de `thread_id`, reset |
| `ui/chat.py` | Renderização do histórico, captura de input, chamada ao backend |
| `ui/debug_panel.py` | Exibição dos metadados de debug da última interação |

`app.py` apenas orquestra os três.

### Por que o `chat_history` existe no `session_state`

O histórico "oficial" vive no MongoDB (via checkpointer). O `session_state.chat_history` é uma cópia local para renderização. Isso evita uma consulta ao banco a cada re-render do Streamlit (que acontece a cada interação do usuário).

Quando o `thread_id` muda (nova conversa ou troca de cliente), o `chat_history` local é zerado — e se o thread já existia no banco (ex: usuário voltou à sessão anterior), ele pode ser reconstruído a partir do backend.

### O painel de debug como ferramenta de apresentação

O `st.expander` está fechado por padrão. A recomendação é abri-lo no momento da apresentação em que a explicação chegar em "como a memória funciona por baixo". Abrindo o expander após uma pergunta sobre cobertura, o avaliador vê:
- Quais cláusulas o vector search retornou e com qual score
- O que estava na memória de longo prazo antes da resposta
- Se um fato novo foi gravado nesta interação

Isso transforma a demo de uma caixa-preta em uma demonstração explícita da arquitetura.

---

## 9. Modelo de dados no MongoDB

### Quatro coleções, dois regimes de gestão

| Coleção | Gerenciada por | Descrição |
|---|---|---|
| `short_term_memory` | LangGraph (MongoDBSaver) | Checkpoints da conversa por `thread_id` |
| `long_term_memory` | LangGraph (MongoDBStore) | Fatos persistentes por `customer_id` |
| `policy_clauses` | Aplicação (seed + pymongo) | Cláusulas do contrato com embeddings |
| `customer_profile` | Aplicação (seed + pymongo) | Perfis, apólices e sinistros dos clientes |

As coleções gerenciadas pelo LangGraph têm schema interno — não devem ser editadas manualmente. As coleções gerenciadas pela aplicação têm schema explícito definido nos arquivos JSON de seed.

### Por que embeddings ficam no mesmo documento que o texto

O documento de `policy_clauses` armazena o texto da cláusula e seu embedding no mesmo documento. Isso tem uma consequência importante: o pipeline de `$vectorSearch` pode retornar o texto junto com o score de similaridade em uma única operação de aggregation, sem necessidade de um segundo lookup por `_id`. Para uma coleção de 10-100 cláusulas, o tamanho do campo `embedding` (1536 floats × 8 bytes ≈ 12KB por documento) é completamente negligenciável.

---

## 10. Integração MCP — rede de oficinas parceiras

### O que é o MCP (Model Context Protocol)

MCP é um protocolo aberto criado pela Anthropic para padronizar a forma como agentes de IA se conectam a sistemas externos. Em vez de cada integração ter sua própria API, o MCP define um contrato uniforme de "tools" que qualquer agente compatível pode descobrir e invocar.

**Por que usar MCP aqui, e não uma função Python direta?**

A demo poderia simplesmente importar as funções do servidor e chamá-las diretamente. Mas isso não demonstra o ponto arquitetural mais importante: em produção, o sistema de oficinas parceiras pertence a um terceiro — fora do codebase, fora da governança da seguradora. O MCP simula esse desacoplamento real: o agente conhece apenas o **contrato** da tool (nome, parâmetros, descrição), nunca a implementação.

### O servidor MCP (`mcp_servers/workshop_server.py`)

Implementado com `FastMCP` (parte do SDK oficial `mcp`). Expõe duas tools:

**`buscar_oficinas_proximas(cep, tipo_servico)`** — retorna até 3 oficinas do mock ordenadas por distância. O mock usa CEP apenas como metadado; distâncias são geradas aleatoriamente para simular a variação real.

**`consultar_agenda_pericia(oficina_id, urgencia)`** — retorna 3 slots de horário disponíveis. `urgencia=urgente` começa a contar a partir de 1 dia, `normal` a partir de 2.

O servidor roda como **processo separado via stdio**: quando o agente inicializa o `MultiServerMCPClient`, ele executa `python mcp_servers/workshop_server.py` como subprocesso e se comunica via stdin/stdout JSON-RPC.

### Integração com o grafo (roteamento condicional)

O LLM no nó `reasoning` recebe as tools vinculadas via `llm.bind_tools(workshop_tools)`. Quando o cliente pergunta sobre oficinas ou agendamento, o LLM decide chamar uma tool e retorna um `AIMessage` com `tool_calls` preenchido (mas sem `content`).

O roteamento usa uma função condicional simples:

```python
def route_after_reasoning(state) -> Literal["find_workshop", "save_memory"]:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "find_workshop"
    return "save_memory"
```

Isso evita dependência do helper `tools_condition` do LangGraph (que roteia para `END` no caminho sem tools, incompatível com nosso `save_memory` final).

### Fluxo de uma mensagem com tool call

1. Usuário: _"Abri um sinistro de colisão, qual oficina perto de mim atende?"_
2. `reasoning`: LLM identifica intenção → retorna `AIMessage(tool_calls=[buscar_oficinas_proximas(cep="04538-133", tipo_servico="colisao")])`
3. `find_workshop` (ToolNode): chama o servidor MCP → recebe lista de oficinas → adiciona `ToolMessage` a `messages`
4. `final_response`: LLM vê as oficinas nos `messages` → compõe resposta natural mencionando nome e distância → extrai fato se houver
5. `save_memory`: persiste fato se identificado
6. `invoke()` retorna resposta + `workshop_results` (extraídos dos ToolMessages) para o painel de debug

### O que demonstra na apresentação

Esse é o momento em que o agente deixa de ser puramente consultivo e passa a **agir sobre um sistema externo**. Vale contrastar explicitamente:
- Antes: agente consulta memória e cláusulas (dados passivos)
- Agora: agente invoca uma ferramenta de um sistema parceiro via protocolo padronizado

Abrir o painel de debug após uma pergunta de oficina mostra a seção "Resultado das ferramentas MCP" com os dados brutos que vieram do servidor antes da composição da resposta final.

---

## 11. Decisões de design e trade-offs

| Decisão | Escolha feita | Trade-off |
|---|---|---|
| Orquestração do agente | LangGraph com fluxo explícito | Mais verboso que agente ReAct, mas previsível e auditável |
| Nós sequenciais vs. paralelos | Sequencial | Mais simples de explicar; em produção, paralelizar load_memory + vector_search reduziria latência |
| Extração de fatos | Segunda chamada ao LLM com JSON | +1 round-trip por mensagem, mas mais simples que function calling formal |
| Retorno de `invoke()` | `dict` com `response` + `debug` | Resolve gap entre specs; acoplamento mínimo, a UI só usa o que precisa |
| Embeddings | `text-embedding-3-small` (OpenAI) | Consistente com o LLM já usado; Voyage AI seria opção com melhor custo/qualidade para produção |
| Filtragem por categoria | Só quando cliente tem 1 tipo de apólice | Demonstra o filtro sem risco de excluir resultados para clientes com múltiplas apólices |
| Histórico local na UI | `session_state.chat_history` como cache | Evita re-query ao Mongo a cada render; aceita risco de divergência (improvável na demo) |
| Ciclo de vida do MCP | Subprocesso por invocação | +~150ms por mensagem; evita complexidade de gerenciar processo global para a demo |
| Transporte MCP | stdio | Sem porta de rede para gerenciar; adequado para demo local; SSE seria melhor para multiprocesso |
