# Guia de Configuração e Execução — ClaraSeg

Este guia cobre tudo que é necessário para colocar a solução rodando do zero, incluindo a configuração do MongoDB Atlas, a criação do índice de vector search e a integração MCP com o servidor de oficinas parceiras.

---

## Pré-requisitos

Antes de começar, verifique que você tem:

- **Python 3.11 ou superior**
  ```bash
  python --version  # deve mostrar 3.11.x ou superior
  ```
- **Conta no MongoDB Atlas** com um cluster ativo (M0 gratuito é suficiente para a demo)
- **Chave de API da OpenAI** com acesso aos modelos `gpt-4o-mini` e `text-embedding-3-small`
- **pip** atualizado
  ```bash
  pip install --upgrade pip
  ```

---

## Etapa 1 — Clonar/abrir o projeto

Se você está lendo este guia dentro do diretório `claraseg/`, você já está no lugar certo. A estrutura deve ser:

```
claraseg/
├── app.py
├── requirements.txt
├── .env.example
├── data/
├── mcp_servers/
│   └── workshop_server.py
├── src/
├── ui/
└── tests/
```

---

## Etapa 2 — Criar e ativar um ambiente virtual

É fortemente recomendado usar um ambiente virtual para isolar as dependências.

```bash
# Dentro do diretório claraseg/
python -m venv .venv
```

**Ativar no macOS/Linux:**
```bash
source .venv/bin/activate
```

**Ativar no Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

Você saberá que está ativo quando o prompt mostrar `(.venv)` no início.

---

## Etapa 3 — Instalar as dependências

```bash
pip install -r requirements.txt
```

Isso instala todos os pacotes necessários:
- `langgraph`, `langgraph-checkpoint-mongodb`, `langgraph-store-mongodb` — orquestração e memória
- `langchain-openai`, `langchain-core` — integração com OpenAI via LangChain
- `langchain-mcp-adapters` — converte tools MCP em tools LangChain
- `mcp` — SDK oficial do Model Context Protocol (servidor de oficinas)
- `pymongo` — driver MongoDB
- `openai` — API de embeddings
- `python-dotenv` — carregamento do `.env`
- `streamlit` — interface web

A instalação pode levar 1-2 minutos.

---

## Etapa 4 — Configurar o MongoDB Atlas

### 4.1 Criar um cluster (se ainda não tiver)

1. Acesse [cloud.mongodb.com](https://cloud.mongodb.com)
2. Clique em **"Create"** → **"M0 Free"** (suficiente para a demo)
3. Escolha a região mais próxima de você
4. Dê um nome ao cluster (ex: `claraseg-demo`) e clique em **"Create Deployment"**
5. Aguarde o cluster provisionar (1-3 minutos)

### 4.2 Criar um usuário de banco de dados

1. No painel do Atlas, vá em **"Database Access"** (menu lateral esquerdo, seção Security)
2. Clique em **"Add New Database User"**
3. Escolha **"Password"** como método de autenticação
4. Defina um usuário (ex: `claraseg-user`) e uma senha forte — **anote a senha**, ela será usada na URI
5. Em "Database User Privileges", selecione **"Read and write to any database"**
6. Clique em **"Add User"**

### 4.3 Configurar acesso de rede

1. No painel do Atlas, vá em **"Network Access"** (menu lateral esquerdo, seção Security)
2. Clique em **"Add IP Address"**
3. Clique em **"Add Current IP Address"** para permitir sua máquina atual
   - Alternativa para demo: **"Allow Access from Anywhere"** (`0.0.0.0/0`) — mais fácil, menos seguro, aceitável para demo
4. Clique em **"Confirm"**

### 4.4 Obter a connection string

1. No painel do Atlas, clique em **"Connect"** no seu cluster
2. Selecione **"Drivers"**
3. Selecione **Python** / versão **3.6 ou superior**
4. Copie a connection string. Ela terá o formato:
   ```
   mongodb+srv://<username>:<password>@<cluster>.mongodb.net/
   ```
5. Substitua `<username>` e `<password>` pelas credenciais criadas no passo 4.2

---

## Etapa 5 — Criar o arquivo `.env`

Na raiz do diretório `claraseg/`, copie o arquivo de exemplo:

```bash
cp .env.example .env
```

Abra o `.env` em qualquer editor de texto e preencha os valores:

```env
MONGODB_URI=mongodb+srv://claraseg-user:SUA_SENHA@seu-cluster.mongodb.net/
MONGODB_DB_NAME=claraseg
OPENAI_API_KEY=sk-proj-...
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
VECTOR_INDEX_NAME=policy_clauses_vector_index
```

**Atenção:**
- `MONGODB_URI` deve terminar com `/` antes dos parâmetros opcionais
- `OPENAI_API_KEY` começa com `sk-` — obtenha em [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- `MONGODB_DB_NAME` pode ser qualquer nome; `claraseg` é o padrão

---

## Etapa 6 — Popular o banco de dados (seed)

Este script cria as coleções `policy_clauses` e `customer_profile`, insere os dados de exemplo e **gera os embeddings** para cada cláusula usando a API da OpenAI.

```bash
# Execute a partir do diretório claraseg/
python -m src.seed
```

Saída esperada:
```
[seed] 3 customer profiles inseridos
[seed] gerando embedding para: auto_cobertura_colisao_01
[seed] gerando embedding para: auto_cobertura_terceiros_02
[seed] gerando embedding para: auto_assistencia_24h_03
[seed] gerando embedding para: auto_carro_reserva_04
[seed] gerando embedding para: auto_cobertura_roubo_05
[seed] gerando embedding para: auto_franquia_06
[seed] gerando embedding para: sinistro_prazo_acionamento_07
[seed] gerando embedding para: sinistro_exclusoes_08
[seed] gerando embedding para: auto_bonus_portabilidade_09
[seed] gerando embedding para: residencial_incendio_10
[seed] 10 cláusulas inseridas com embeddings
[seed] concluído
```

Isso faz 10 chamadas à API da OpenAI (uma por cláusula) e grava os documentos no Atlas. O seed usa `collection.drop()` antes de inserir, então pode ser re-executado para resetar o estado inicial.

**Possíveis erros:**
- `KeyError: 'MONGODB_URI'` → o arquivo `.env` não foi encontrado ou tem erro de sintaxe
- `pymongo.errors.ServerSelectionTimeoutError` → URI incorreta ou IP não liberado no Atlas (Etapa 4.3)
- `openai.AuthenticationError` → chave de API inválida

---

## Etapa 7 — Criar o índice de Vector Search no Atlas

Este é o único passo manual obrigatório que não pode ser automatizado pelo código. O índice precisa existir antes de rodar a aplicação.

### 7.1 Acessar o painel de índices

1. No painel do Atlas, clique no nome do seu cluster para abrir o Data Explorer
2. No menu superior, clique na aba **"Atlas Search"**
3. Clique em **"Create Search Index"**

### 7.2 Configurar o índice

1. Em "Configuration Method", selecione **"JSON Editor"**
2. Selecione o banco de dados: **`claraseg`**
3. Selecione a coleção: **`policy_clauses`**
4. Em "Index Name", digite: `policy_clauses_vector_index`
5. No campo de JSON, substitua o conteúdo por:

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

6. Clique em **"Next"** e depois em **"Create Search Index"**

### 7.3 Aguardar o índice construir

O índice demora entre 30 segundos e 2 minutos para ser construído. O status muda de **"Building"** para **"Active"**. Só prossiga para a próxima etapa quando o status for **"Active"**.

**Importante:** se o seed não foi executado antes de criar o índice, o índice ainda pode ser criado, mas será construído sobre uma coleção vazia. Ele ficará ativo mas não retornará resultados. Execute sempre o seed antes de criar o índice, ou re-indexe após o seed.

---

## Etapa 8 — Verificar o servidor MCP (opcional, mas recomendado)

Antes de rodar a aplicação completa, teste o servidor MCP isoladamente para garantir que o ambiente Python está correto:

```bash
# Verifica se o servidor inicia sem erro (Ctrl+C para encerrar)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python mcp_servers/workshop_server.py
```

Saída esperada (JSON com as duas tools disponíveis):
```json
{"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "buscar_oficinas_proximas", ...}, {"name": "consultar_agenda_pericia", ...}]}}
```

Se aparecer `ModuleNotFoundError: No module named 'mcp'`, o pacote não foi instalado — rode `pip install -r requirements.txt` novamente.

---

## Etapa 9 — Executar os smoke tests

Antes de rodar a interface, valide que o backend está funcionando corretamente executando os testes de fluxo ponta a ponta:

```bash
python -m tests.test_agent_smoke
```

Os testes cobrem 8 critérios de aceite do projeto:
1. Memória de longo prazo persiste entre sessões diferentes
2. Memória de curto prazo funciona dentro da mesma sessão
3. `vector_search_clausulas` retorna cláusulas relevantes para 3 formulações distintas
4. Status de sinistro é retornado corretamente do perfil do cliente
5. O agente não inventa cobertura inexistente
6. **Eficiência de tool calling:** pergunta factual (número de apólice) não aciona nenhuma tool
7. **Precisão de tool calling:** pergunta de cobertura aciona exatamente 1 chamada a `vector_search_clausulas`
8. **Integração MCP + ReAct:** pergunta combinada (cobertura + oficina) aciona ambas as tools no mesmo turno

Saída esperada (pode demorar 90-120 segundos):
```
=== ClaraSeg — Smoke Tests ===

1. Memória de longo prazo entre sessões
   [thread A] resposta: Entendido, Carlos! Vou registrar que você trocou ...
   [thread A] novo fato: {'fact': 'Cliente trocou de veículo, novo carro é um Compass 2025', ...}
   [thread B] resposta: Olá! Sim, registro que você trocou para um Compass 2025 ...
   PASSOU

2. Memória de curto prazo (dentro do mesmo thread)
   resposta: Sim, o Toyota Corolla 2023 que você mencionou tem cobertura de roubo ...
   PASSOU

3. Vector search semântico (tool vector_search_clausulas chamada)
   'O que acontece se bater o carro?' → 3 cláusulas
   'Tenho direito a veículo emprestado enquanto o meu está na oficina?' → 3 cláusulas
   'Qual o prazo para eu avisar a seguradora depois de um acidente?' → 3 cláusulas
   PASSOU

4. Status de sinistro do customer_profile
   resposta: Carlos, seu sinistro CLM-4471 referente à colisão traseira ...
   PASSOU

5. Não alucinação de cobertura inexistente
   resposta: Infelizmente, com base nas cláusulas disponíveis, não identifico cobertura ...
   PASSOU

6. Pergunta factual não dispara tool call
   resposta: Olá Carlos! O número da sua apólice de auto é AUTO-2023-001 ...
   tool calls feitas: []
   PASSOU

7. Pergunta de cobertura dispara exatamente 1 chamada a vector_search_clausulas
   resposta: Consultei as cláusulas e ... colisão com animal ...
   chamadas a vector_search_clausulas: 1
   PASSOU

8. Pergunta combinada dispara vector_search_clausulas e buscar_oficinas_proximas
   resposta: Verifiquei as cláusulas e encontrei oficinas parceiras próximas ...
   vector_search_clausulas: 1x, buscar_oficinas_proximas: 1x
   PASSOU

=== Todos os testes passaram ===
```

---

## Etapa 10 — Rodar a aplicação

```bash
streamlit run app.py
```

O Streamlit abrirá automaticamente no navegador em `http://localhost:8501`. Se não abrir automaticamente, acesse o endereço manualmente.

**Na primeira carga:**
- A sidebar mostrará o dropdown com os 3 clientes fictícios
- Um `thread_id` é gerado automaticamente
- O chat estará vazio (nova sessão)

---

## Fluxo de demonstração recomendado

### Parte 1 — Vector Search (2-3 min)

1. Selecione **"Carlos Mendonça"** na sidebar
2. Envie: _"Meu carro foi atingido por trás num estacionamento. O que eu faço?"_
3. Abra o painel de debug — mostre as 3 cláusulas recuperadas e os scores
4. Envie: _"Tenho direito a carro reserva enquanto o meu está na oficina?"_
5. Mostre que uma pergunta formulada diferente ainda recuperou a cláusula correta

### Parte 2 — Memória de curto prazo (1-2 min)

6. Envie: _"E quanto à franquia? Ela é descontada do valor do reparo?"_
7. Observe que o agente manteve o contexto de "colisão" das mensagens anteriores — não foi necessário repetir

### Parte 3 — Memória de longo prazo (2-3 min)

8. Envie: _"Acabei de trocar de carro, agora tenho um Compass 2025."_
9. Mostre no painel de debug que um **novo fato foi gravado**
10. Clique em **"Nova conversa"** na sidebar — o chat zera
11. Envie: _"Qual é o meu carro atual?"_
12. O agente responde com o Compass 2025 mesmo em uma sessão nova — mostre os **fatos de longo prazo** no painel de debug

### Parte 4 — Dado operacional (1 min)

13. Envie: _"Qual o status do meu sinistro aberto?"_
14. Mostre que a resposta vem do `customer_profile` (não da memória do agente)

### Parte 5 — Integração MCP e ReAct loop (2-3 min)

15. Envie: _"Abri um sinistro de colisão. O que a apólice cobre e tem alguma oficina parceira perto de mim?"_
16. Aguarde — esta mensagem aciona o **loop ReAct**: o agente chama `vector_search_clausulas`, vê o resultado, então chama `buscar_oficinas_proximas`, e finalmente compõe uma resposta unificada
17. Abra o painel de debug — mostre a seção "Tool calls deste turno" com **duas** entradas: cláusulas com scores e oficinas com distâncias
18. Envie: _"Qual a disponibilidade de agenda na mais próxima?"_
19. O agente chama `consultar_agenda_pericia` e retorna horários disponíveis
20. Destaque o contraste arquitetural: todas as ferramentas (busca semântica local, servidor MCP de oficinas) passam pelo **mesmo** `tools_node` — o agente decide a sequência de chamadas dinamicamente

---

## Solução de problemas comuns

### "No module named 'src'"

Execute os comandos sempre a partir do diretório `claraseg/`, não de um subdiretório:
```bash
cd /caminho/para/claraseg
python -m src.seed   # correto
```

### Vector search retorna lista vazia

Causas possíveis (em ordem de probabilidade):
1. O índice ainda está sendo construído — aguarde o status ficar **"Active"** no Atlas
2. O nome do índice no `.env` não bate com o criado no Atlas — verifique `VECTOR_INDEX_NAME`
3. O seed não foi executado antes da criação do índice — re-execute o seed e aguarde o índice re-indexar

### "OperationFailure: PlanExecutor error during aggregation"

O índice de vector search ainda não existe ou está com nome diferente. Verifique o nome em `VECTOR_INDEX_NAME` no `.env`.

### Agente não lembra fatos entre sessões

O MongoDBStore pode não ter persistido o fato. Verifique:
1. Se a mensagem que menciona o fato foi suficientemente explícita (ex: "troquei de carro" é explícito; "estou pensando em trocar" pode não ser classificado como fato duradouro)
2. Se o painel de debug mostrou "Novo fato gravado" após a mensagem — se não mostrou, o LLM não classificou como fato duradouro

### Streamlit recarrega e perde o histórico do chat

O `chat_history` em `session_state` é perdido ao recarregar a página (F5). Isso é comportamento esperado — o histórico oficial está no MongoDB. Para uma demo, evite F5; use o botão "Nova conversa" para controlar sessões.

### Agente não chama as tools de oficina

Possíveis causas:
1. **O LLM não reconheceu intenção de busca de oficina** — reformule: _"Preciso de uma oficina parceira para reparar o carro após o sinistro de colisão"_ é mais explícito que _"tem alguma oficina?"_
2. **`ModuleNotFoundError: mcp`** durante a invocação — `pip install -r requirements.txt` novamente
3. **Erro de subprocess** — verifique se `python mcp_servers/workshop_server.py` roda sem erros no terminal

### `RuntimeError: This event loop is already running`

Ocorre se o Streamlit estiver rodando em modo async (versões antigas). Solução: atualizar o Streamlit para `>=1.38.0` ou adicionar `import nest_asyncio; nest_asyncio.apply()` no topo de `app.py`.

### Tool call retorna oficinas inventadas (alucinação)

O LLM não deveria inventar — o sistema prompt instrui explicitamente a usar apenas dados das ferramentas. Se acontecer, é um caso raro de alucinação. Para a demo: repetir a pergunta ou reformular para ser mais direta sobre buscar oficinas parceiras.

---

## Comandos de referência rápida

```bash
# Ativar ambiente virtual
source .venv/bin/activate

# Re-popular o banco (reseta dados)
python -m src.seed

# Testar o servidor MCP isoladamente
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python mcp_servers/workshop_server.py

# Rodar testes ponta a ponta
python -m tests.test_agent_smoke

# Subir a interface
streamlit run app.py

# Verificar se o .env está carregando corretamente
python -c "from src.config import MONGODB_URI, OPENAI_API_KEY; print('OK')"
```
