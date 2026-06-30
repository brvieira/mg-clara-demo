# ClaraSeg

Agente conversacional de atendimento ao cliente para a **Vivaz Seguros** (seguradora fictícia), construído como demonstração técnica de LangGraph + MongoDB Atlas Vector Search.

A Clara responde perguntas sobre cobertura de apólice e status de sinistro em linguagem natural, mantendo memória de curto e longo prazo e buscando cláusulas contratuais por similaridade semântica.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     app.py (Streamlit)                      │
│         sidebar.py  ──  chat.py  ──  debug_panel.py         │
└────────────────────────┬────────────────────────────────────┘
                         │ invoke(thread_id, customer_id, msg)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      src/agent.py                           │
│      (async internamente; asyncio.run() na borda pública)   │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │  MultiServerMCP     │── stdio ──► mcp_servers/
              │  Client             │            workshop_server.py
              └──────────┬──────────┘            (subprocesso)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              LangGraph StateGraph (src/graph/)              │
│                                                             │
│  START → load_memory → reasoning ←──────────────────┐      │
│                            │                        │      │
│                     [tools_condition]          tools_node   │
│                            │ sem tools          (ToolNode)  │
│                            ↓                        │      │
│                       save_memory              tool call   │
│                            │                               │
│                           END                              │
└─────────┬───────────────────┬───────────────────────────────┘
          │                   │
          ▼                   ▼
┌──────────────────┐  ┌──────────────────────────────────────┐
│  MongoDB Atlas   │  │          OpenAI API                  │
│                  │  │                                      │
│  short_term_     │  │  gpt-4o-mini                         │
│  memory          │  │  (reasoning + extração de fatos)     │
│  (checkpointer)  │  │                                      │
│                  │  │  text-embedding-3-small               │
│  long_term_      │  │  (embeddings para vector search)     │
│  memory          │  └──────────────────────────────────────┘
│  (store)         │
│                  │
│  policy_clauses  │
│  (vector search) │
│                  │
│  customer_       │
│  profile         │
└──────────────────┘
```

### Fluxo de execução por turno

1. **`load_memory`** — carrega fatos de longo prazo do cliente (`MongoDBStore`) e perfil operacional (`customer_profile`).
2. **`reasoning`** — o LLM recebe o system prompt com perfil + fatos e decide: chamar tool(s) ou responder diretamente.
3. **`tools_node`** — se o LLM emitiu tool calls, executa as ferramentas e adiciona os resultados como `ToolMessage`. Volta para `reasoning`.
4. **`save_memory`** — ao final (sem mais tool calls), persiste fato novo no `MongoDBStore` se a resposta indicar um.

---

## Componentes técnicos

### Memória de curto prazo — `MongoDBSaver` (checkpointer)

O estado completo do grafo (incluindo o histórico de `messages`) é persistido após cada nó via `langgraph-checkpoint-mongodb`. A chave é o `thread_id`:

```
thread_id = "{customer_id}_{uuid_hex[:8]}"
```

Nova conversa = novo `thread_id` = histórico zerado. O histórico não é reenviado pela UI a cada turno — o LangGraph o recupera automaticamente do MongoDB antes de cada invocação.

### Memória de longo prazo — `MongoDBStore`

Fatos duradouros sobre o cliente (mudança de veículo, endereço, preferência de contato) são persistidos via `langgraph-store-mongodb` com namespace `(customer_id, "facts")`.

O nó `reasoning` faz uma segunda chamada ao LLM ao final de cada turno para classificar se a mensagem contém um fato novo. Retorna JSON estruturado:

```json
{"has_fact": true, "key": "vehicle_change", "fact": "Cliente trocou para Compass 2025"}
```

O `MongoDBStore` é **independente do `thread_id`** — fatos persistem entre sessões distintas do mesmo cliente.

### Atlas Vector Search

Cláusulas da apólice ficam na coleção `policy_clauses` com embeddings gerados por `text-embedding-3-small` (1536 dimensões). A busca usa `$vectorSearch` na pipeline de aggregation:

```python
{"$vectorSearch": {
    "index": VECTOR_INDEX_NAME,
    "path": "embedding",
    "queryVector": query_embedding,
    "numCandidates": 50,
    "limit": 3,
}}
```

Clientes com um único tipo de apólice recebem filtro automático por `category` ("auto" ou "residencial"), demonstrando pre-filtering combinado com vector search.

O índice precisa ser criado manualmente na Atlas UI (criação programática não é suportada via driver pymongo para índices de search).

### Integração MCP — rede de oficinas

O servidor `mcp_servers/workshop_server.py` (implementado com `FastMCP`) roda como subprocesso via stdio e expõe duas tools:

- **`buscar_oficinas_proximas(cep, tipo_servico)`** — retorna até 3 oficinas parceiras ordenadas por distância.
- **`consultar_agenda_pericia(oficina_id, urgencia)`** — retorna 3 slots disponíveis para perícia.

O agente conhece apenas o contrato das tools (nome, parâmetros, descrição), nunca a implementação — simulando uma integração real com sistema externo de terceiro.

O subprocesso é iniciado e encerrado a cada invocação (`async with MultiServerMCPClient`). Custo: ~150ms por mensagem.

---

## Modelo de dados (MongoDB)

| Coleção | Gerenciada por | Conteúdo |
|---|---|---|
| `short_term_memory` | LangGraph (`MongoDBSaver`) | Checkpoints da conversa por `thread_id` |
| `long_term_memory` | LangGraph (`MongoDBStore`) | Fatos persistentes por `customer_id` |
| `policy_clauses` | Aplicação (seed) | Cláusulas contratuais com embeddings |
| `customer_profile` | Aplicação (seed) | Apólices, sinistros e dados cadastrais |

As coleções gerenciadas pelo LangGraph têm schema interno — não devem ser editadas manualmente.

---

## Interface Streamlit

| Módulo | Responsabilidade |
|---|---|
| `ui/sidebar.py` | Seleção de cliente e controle de `thread_id` |
| `ui/chat.py` | Renderização do histórico e captura de input |
| `ui/debug_panel.py` | Painel de transparência com dados de cada interação |

O painel de debug (expandível) exibe: cláusulas retornadas pelo vector search com score de similaridade, fatos de longo prazo usados na resposta e fato novo gravado — tornando a arquitetura visível durante a demonstração.

---

## Setup

### Pré-requisitos

- Python 3.11+
- Cluster MongoDB Atlas com Atlas Vector Search habilitado
- Chave de API OpenAI

### Instalação

```bash
cd claraseg
pip install -r requirements.txt
cp .env.example .env
# preencher MONGODB_URI, OPENAI_API_KEY e MONGODB_DB_NAME no .env
```

### Seed do banco

```bash
python -m src.seed
```

Popula `customer_profile` e `policy_clauses` (com embeddings gerados via OpenAI).

### Índice de vector search

Crie manualmente na Atlas UI:

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

Selecione a coleção `policy_clauses` e nomeie o índice conforme `VECTOR_INDEX_NAME` no `.env`.

### Executar

```bash
streamlit run app.py
```

---

## Stack

| Camada | Tecnologia |
|---|---|
| Interface | Streamlit |
| Orquestração do agente | LangGraph |
| Memória curto prazo | `langgraph-checkpoint-mongodb` |
| Memória longo prazo | `langgraph-store-mongodb` |
| Banco de dados | MongoDB Atlas |
| Busca semântica | Atlas Vector Search |
| LLM e embeddings | OpenAI (`gpt-4o-mini`, `text-embedding-3-small`) |
| Integração externa | MCP via `langchain-mcp-adapters` + `FastMCP` |

---

## Escopo e limitações

Esta demo cobre exclusivamente os fluxos consultivos/informativos definidos no exercício técnico. Estão fora do escopo:

- Autenticação real de usuário (cliente selecionado manualmente na sidebar)
- Ações transacionais (abertura de sinistro, alteração de dados)
- Guardrails formais e avaliação automatizada de qualidade de resposta
- Reranking dos resultados de busca semântica
