# ClaraSeg

**Um agente de atendimento ao cliente com memória, RAG e ações reais — não apenas um chatbot de FAQ.**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![LangGraph](https://img.shields.io/badge/LangGraph-orquestração-1C3C3C)
![MongoDB Atlas](https://img.shields.io/badge/MongoDB_Atlas-Vector_Search-47A248?logo=mongodb&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## 💡 Sobre o Projeto

ClaraSeg é uma demonstração técnica de um agente conversacional em português para a **Vivaz Seguros**, uma
seguradora fictícia. A "Clara" resolve o problema central de atendimento em seguros: responder dúvidas de
cobertura contratual e status de sinistro exige cruzar **linguagem natural**, **texto contratual longo** (apólices
em PDF) e **sistemas transacionais de terceiros** (oficinas parceiras, agendamento de perícia) — algo que FAQs
estáticas e chatbots baseados em regras não resolvem bem.

O agente entrega:
- Respostas ancoradas nas cláusulas reais da apólice do cliente (não alucinadas), via busca semântica.
- Continuidade entre conversas: lembra fatos duráveis do cliente (troca de veículo, mudança de endereço) mesmo em uma nova sessão.
- Capacidade de agir, não só informar: consulta oficinas próximas, agenda/altera/cancela perícias e cria/atualiza apólices através de servidores MCP externos.

## 🚀 Funcionalidades Principais

- 💬 **Chat com streaming** token a token (SSE) com painel de transparência mostrando cada tool call em tempo real.
- 📄 **Busca semântica em cláusulas de apólice** (Atlas Vector Search) a partir de PDFs reais, ingeridos via Docling.
- 🧠 **Memória de curto prazo** (histórico da conversa por `thread_id`) e **de longo prazo** (fatos duráveis por cliente, persistem entre sessões).
- 🔧 **Integração via MCP** com dois servidores simulando sistemas parceiros: rede de oficinas (`workshop-mcp`) e gestão de apólices (`policy-mcp`).
- 👤 **Sidebar de clientes e perfil** servidos por uma API Node.js dedicada e somente-leitura (`customer-api`), desacoplada do agente.
- 🐳 **Stack 100% containerizada** via `docker-compose`, com cada serviço em sua própria imagem.

## 🛠️ Tecnologias Utilizadas

| Camada | Tecnologia |
|---|---|
| Orquestração do agente | LangGraph (grafo de estados: `load_memory → reasoning ↔ tools_node → save_memory`) |
| LLM / embeddings | OpenAI `gpt-4o-mini` + `text-embedding-3-small` |
| Memória curto/longo prazo | `langgraph-checkpoint-mongodb` / `langgraph-store-mongodb` |
| Banco de dados | MongoDB Atlas + Atlas Vector Search |
| Ingestão de PDFs | Docling (`HybridChunker`) |
| API do agente | FastAPI (`/health`, `/chat`, `/chat/stream` via SSE) |
| Ferramentas externas | MCP (`FastMCP`, transporte HTTP/streamable-http) |
| API de clientes | Node.js + Express + TypeScript |
| Frontend | React 19 + Vite + TypeScript + Tailwind + Zustand |
| Infraestrutura | Docker / Docker Compose, Nginx (serve o build do webapp) |

## 📦 Estrutura de Pastas

```
mg-demo/
├── .env.example
├── .gitignore
├── CLAUDE.md
├── README.md
├── docker-compose.yml
├── logotipo.png
├── requirements.txt
│
├── ai-agent/                          # Backend do agente: grafo LangGraph, memória, tools, API FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── agent.py                   # invoke()/astream() — único ponto de acoplamento externo
│   │   ├── api.py                     # FastAPI: /health, /chat, /chat/stream
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── embeddings.py
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   ├── build.py               # Definição do StateGraph
│   │   │   ├── nodes.py               # load_memory, reasoning, save_memory + system prompt
│   │   │   └── state.py
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── checkpointer.py        # MongoDBSaver (curto prazo)
│   │   │   └── store.py               # MongoDBStore (longo prazo)
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── mcp_client.py          # MultiServerMCPClient (workshop-mcp, policy-mcp)
│   │       └── vector_search.py       # vector_search_clausulas
│   └── tests/
│       └── test_agent_smoke.py
│
├── customer-api/                      # API Node/Express somente-leitura sobre customer_profile
│   ├── .env.example
│   ├── .gitignore
│   ├── Dockerfile
│   ├── package-lock.json
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── db.ts
│       └── server.ts                  # GET /clients, GET /clients/:customerId
│
├── policy-mcp/                        # Servidor MCP — criação/atualização de apólices
│   ├── Dockerfile
│   ├── policy_server.py
│   └── requirements.txt
│
├── workshop-mcp/                      # Servidor MCP — rede de oficinas parceiras e agendamento
│   ├── Dockerfile
│   ├── requirements.txt
│   └── workshop_server.py
│
├── webapp/                            # SPA React (chat, sidebar de clientes, painel de debug)
│   ├── .dockerignore
│   ├── .env.example
│   ├── .gitignore
│   ├── .oxlintrc.json
│   ├── Dockerfile
│   ├── README.md
│   ├── components.json
│   ├── index.html
│   ├── nginx.conf
│   ├── package-lock.json
│   ├── package.json
│   ├── tsconfig.app.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── public/
│   │   ├── favicon.svg
│   │   └── icons.svg
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── index.css
│       ├── types.ts
│       ├── vite-env.d.ts
│       ├── assets/
│       │   ├── logo.svg
│       │   └── logotipo.png
│       ├── components/
│       │   ├── AppHeader.tsx
│       │   ├── ChatBubble.tsx
│       │   ├── ChatPanel.tsx
│       │   ├── ClientCard.tsx
│       │   ├── ClientProfileDialog.tsx
│       │   ├── ClientSidebar.tsx
│       │   ├── CollapsedRail.tsx
│       │   ├── DebugPanel.tsx
│       │   ├── LongTermFactsPanel.tsx
│       │   ├── ToolCallCard.tsx
│       │   ├── TypingIndicator.tsx
│       │   └── ui/                    # avatar, badge, button, card, dialog, input,
│       │                               # scroll-area, separator, tabs, tooltip (shadcn)
│       ├── lib/
│       │   ├── api.ts
│       │   ├── format.ts
│       │   ├── sse.ts
│       │   └── utils.ts
│       └── store/
│           └── uiStore.ts
│
├── data/
│   ├── seed.py                        # Popula customer_profile e workshops
│   ├── seed_customer_profiles.json    # (gitignored — fornecido localmente)
│   ├── seed_workshops.json            # (gitignored — fornecido localmente)
│   ├── ingestion/
│   │   └── ingest.py                  # Pipeline de ingestão de PDFs (Docling → chunk → embed → Mongo)
│   └── source_docs/
│       ├── auto/apolice_auto.pdf
│       ├── residencial/apolice_residencial.pdf
│       └── vida/apolice_vida.pdf
│
├── specifications/
│   ├── SPEC_agente_claraseg.md
│   ├── SPEC_interface_claraseg.md
│   └── SPEC_interface_claraseg_v2.md
│
└── documentation/
    ├── DEMO_SCRIPT.md
    ├── SETUP.md
    ├── TECHNICAL.md
    └── context.md
```

> Arquivos de configuração de IDE/OS (`.claude/`, `.DS_Store`) e artefatos gerados
> (`node_modules/`, `.venv/`, `__pycache__/`, `dist/`) foram omitidos por não fazerem
> parte do código-fonte do projeto.

## ⚙️ Pré-requisitos e Instalação

**Pré-requisitos:**
- Python 3.12+
- Node.js 20+
- Docker + Docker Compose (opcional, mas recomendado)
- Cluster MongoDB Atlas com Atlas Vector Search habilitado
- Chave de API OpenAI

**1. Clonar o repositório**

```bash
git clone https://github.com/[SEU_USUARIO]/mg-demo.git
cd mg-demo
```

**2. Configurar variáveis de ambiente**

```bash
cp .env.example .env
# preencher MONGODB_URI, OPENAI_API_KEY e demais variáveis
```

**3a. Rodar tudo via Docker Compose (recomendado)**

```bash
docker compose up
```

Sobe `workshop-mcp` (:8000), `policy-mcp` (:8001), `customer-api` (:8090), `ai-agent` (:8080) e `webapp` (:5173).

**3b. Ou rodar cada serviço localmente**

```bash
# Dependências Python (raiz do repo, para seed/ingestão)
pip install -r requirements.txt

# Servidores MCP
python workshop-mcp/workshop_server.py
python policy-mcp/policy_server.py

# API do agente
cd ai-agent && pip install -r requirements.txt
uvicorn src.api:app --reload --port 8080

# API de clientes
cd customer-api && npm install && npm run dev

# Frontend
cd webapp && npm install && npm run dev
```

**4. Popular o banco**

```bash
python data/seed.py                                          # customer_profile + workshops
python data/ingestion/ingest.py --input-dir data/source_docs  # cláusulas de apólice + embeddings
```

> O índice do Atlas Vector Search **não** pode ser criado via driver — crie-o manualmente na Atlas UI, na
> coleção `policy_chunks`, campo `embedding` (1536 dimensões, cosine), com `metadata.category` como filtro,
> nomeado conforme `VECTOR_INDEX_NAME` no `.env`.

## 🖥️ Como Usar / Exemplos

Com os serviços no ar, acesse a interface em `http://localhost:5173`, selecione um cliente na sidebar e converse
com a Clara.

Chamando a API do agente diretamente:

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST-001", "message": "Minha apólice de auto cobre vidros?"}'
```

Streaming (SSE):

```bash
curl -N -X POST http://localhost:8080/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST-001", "message": "Qual o status do meu sinistro?"}'
```

Principais rotas:

| Serviço | Rota | Descrição |
|---|---|---|
| `ai-agent` | `GET /health` | Healthcheck (ping no Mongo) |
| `ai-agent` | `POST /chat` | Turno completo, resposta única |
| `ai-agent` | `POST /chat/stream` | Resposta em streaming (SSE) |
| `customer-api` | `GET /clients` | Lista resumida de clientes |
| `customer-api` | `GET /clients/:id` | Perfil completo do cliente |

Testes de fumaça ponta a ponta (usa OpenAI + MongoDB reais, ~90-120s):

```bash
cd ai-agent && python -m tests.test_agent_smoke
```

## 🤝 Como Contribuir

1. Faça um **fork** deste repositório.
2. Crie uma branch a partir da `main`: `git checkout -b feature/nome-da-feature`.
3. Faça commits pequenos e descritivos.
4. Rode os testes de fumaça relevantes antes de abrir o PR.
5. Abra um **Pull Request** para a `main` descrevendo o quê e o porquê da mudança.

## 📝 Licença

Não há um arquivo `LICENSE` neste repositório no momento. Recomenda-se adotar a licença **MIT** — crie um
arquivo `LICENSE` na raiz com o texto padrão MIT, atribuído a `[SEU_NOME]`, para tornar isso explícito.
