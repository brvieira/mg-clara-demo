# SPEC v2 — Interface do Agente de IA · Vivaz Seguros (dados reais)

Especificação de implementação para a interface React consumir os **dados e serviços reais** do projeto
(`ai-agent/`, `workshop-mcp/`, `policy-mcp/`, MongoDB) em vez do mock estático da `SPEC_interface_claraseg.md`
original. **O design system (seção 3) é reaproveitado sem alterações** — cores, tipografia, formas e sombras
continuam sendo as da spec original. Tudo o que depende de dados, API, modelos e fluxos foi reescrito para
refletir o backend tal como ele existe hoje.

Este documento substitui, para fins de implementação, as seções 1, 2, 4–11 da spec original. A seção 3
(Design system) daquele documento permanece válida e é apenas referenciada aqui, não duplicada.

---

## 1. Visão geral

Painel de demonstração de um agente de IA (**Clara**) para a Vivaz Seguros (ramos Auto, Residencial e Vida),
com **backend real**: a UI é um cliente HTTP/SSE de `ai-agent/src/api.py`, que por sua vez invoca o grafo
LangGraph descrito em `ai-agent/src/agent.py`. Não há mais dados hardcoded no frontend além de um fallback de
apresentação (seção 9).

Três colunas, igual à spec original:

1. **Seleção de cliente** (esquerda) — lista de clientes reais lidos de `customer_profile` no MongoDB.
2. **Chat** (centro) — conversa real com o agente via `POST /chat/stream` (SSE).
3. **Debug / Ações do agente** (direita) — timeline das tool calls reais feitas pelo agente no turno, construída
   a partir do campo `debug` retornado pela API.

Diferenças-chave em relação à spec original:

- **Não é mais "sem backend"**: a UI depende de `ai-agent` (porta padrão `8080`), `workshop-mcp` (porta `8000`)
  e `policy-mcp` (porta `8001`) estarem no ar, além do MongoDB Atlas seedado (`data/seed.py`) e com o índice de
  vetor criado.
- Os "cenários pré-carregados" viram **roteiros de demonstração** (mensagens sugeridas para digitar), não texto
  congelado — a resposta do agente é sempre gerada ao vivo e pode variar entre execuções.
- O número e os dados dos clientes vêm do seed real (4 clientes, ver seção 9), não dos 4 perfis fictícios da
  spec original.
- Cada cliente pode ter **múltiplas apólices de tipos diferentes** simultaneamente (o modelo `Client` antigo
  assumia uma única "ramo" por cliente — isso não existe mais).

---

## 2. Stack recomendada

Mesma stack da spec original (seção 2 daquele documento): React 18 + Vite + TypeScript, shadcn/ui, Tailwind,
lucide-react, framer-motion, Zustand, dayjs. A regra de reutilização de componentes prontos (`Dialog`, `Avatar`,
`Badge`, `ScrollArea`, `Tabs`, `Button`, `Tooltip`, `Separator`, `Input`) também se mantém.

Adições necessárias para consumir a API real:

| Necessidade                                           | Escolha recomendada                                                                                                                                                                       |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cliente HTTP                                          | `fetch` nativo (sem lib extra)                                                                                                                                                            |
| Consumo de SSE de um endpoint **POST** com corpo JSON | **`@microsoft/fetch-event-source`** (ou parser manual sobre `fetch` + `ReadableStream` — o `EventSource` nativo do browser não suporta `POST`/corpo, então não serve para `/chat/stream`) |
| Variável de ambiente da URL base da API               | `VITE_API_BASE_URL` (ex.: `http://localhost:8080`), lida via `import.meta.env`                                                                                                            |

> **Regra do agente implementador:** nenhuma chamada a Mongo a partir do frontend — todo acesso a dados passa
> pela API HTTP do `ai-agent`. O frontend não conhece nomes de collections do Mongo, apenas o contrato JSON dos
> endpoints descritos na seção 5.

---

## 3. Design system

Segue o **Manual de Identidade Visual da Vivaz Seguros** (paleta oficial roxo/turquesa, tipografia Poppins).

### 3.1 Cores oficiais

**Primárias**

```
--vz-roxo          #4B1D72   /* Roxo Institucional — cor primária, CTAs, avatar/marca, cabeçalho do modal */
--vz-roxo-2        #7B3DBB   /* Roxo Secundário — status "em execução" no debug */
--vz-turquesa      #00A99D   /* Turquesa Vivaz — status "concluído", resultados, destaques positivos */
```

**Secundárias / neutras**

```
--vz-azul-escuro   #0D1B2A   /* texto principal e fundo do painel de debug */
--vz-branco-gelo   #F2F4F7   /* fundo geral (app, chat) */
--vz-branco        #FFFFFF   /* cartões, bolha do agente, header, campos */
```

**Tokens de UI derivados**

```
--vz-accent        #4B1D72   /* = roxo institucional (prop trocável na demo) */
--vz-accent-soft   rgba(75,29,114,.10)
--vz-ink           #0D1B2A   /* texto principal */
--vz-muted         #64748B   /* texto secundário (slate) */
--vz-faint         #94A3B8   /* labels, placeholders (slate claro) */
--vz-border        rgba(13,27,42,.10)
--vz-success       #5C8A5A   /* "online", "em dia", check de coberturas (semáforo positivo) */
--vz-success-ink   #3F6B3E

/* Painel de debug (fundo azul escuro da marca) */
--vz-dbg-bg        #0D1B2A
--vz-dbg-text      #E8ECF3
--vz-dbg-muted     #7C8AA0
--vz-dbg-ok        #00A99D   /* status concluído / resultado / latência → turquesa */
--vz-dbg-run       #7B3DBB   /* status em execução (com pulse) → roxo secundário */
--vz-dbg-code-val  #5FD4C8   /* valores no bloco de código (turquesa claro) */
--vz-dbg-code-bg   rgba(0,0,0,.28)
```

Configure como CSS variables e/ou tokens do `tailwind.config`. A cor de acento (`--vz-accent`) deve ser um prop/tema trocável — o padrão é o **Roxo Institucional #4B1D72**.

### 3.2 Tipografia (Google Fonts)

Fonte oficial da marca: **Poppins** (pesos 300/400/500/600/700).

- **Títulos / marca:** `Poppins` SemiBold–Bold (600/700) — nome no modal, iniciais dos avatares, títulos.
- **UI / corpo:** `Poppins` Regular/Medium (400/500) — todo o texto de interface.
- **Legendas:** `Poppins` Light (300).
- **Monoespaçada:** `IBM Plex Mono` (400/500/600) — nº de apólice, CPF, telefone, sessão, e todo o painel de debug (nomes de tool, código de parâmetros, timestamps, latência).

Escala: título de cliente 14–15px · corpo do chat 14px · labels 10–11px uppercase com `letter-spacing`. Nada abaixo de 10px.

### 3.3 Logotipo

- **Logo completo** (`vivaz-logo.png`, símbolo V + wordmark "vivaz seguros", fundo transparente): usado no **header**, altura ~30px.
- **Símbolo isolado** (`vivaz-mark.png`, o "V" roxo/turquesa, fundo transparente): usado nos **avatares do agente** (dentro de um quadrado branco arredondado) e onde couber uma marca compacta.
- Conceito: "V" estilizado por duas formas arredondadas (roxo = confiança/estabilidade; turquesa = proximidade/inovação; sobreposição = colaboração).
- Área de proteção e fundo claro; nunca aplicar o logo sobre fundos que reduzam o contraste do wordmark roxo.

### 3.4 Formas e sombras

- Raios: cartões `12–13px`, botões `9–10px`, bolhas de chat `16px` (com um canto "rabo" reduzido a `4–5px`), pills/badges `99px`.
- Sombras suaves: `0 1px 3px rgba(13,27,42,.06)` (cartões), `0 2px 8px rgba(75,29,114,.28)` (CTA acento roxo).
- Espaçamentos base do manual: XS 4 · SM 8 · MD 16 · LG 24 · XL 32 · XXL 48 (px).
- Ícones: estilo outline, cantos arredondados, minimalista (ex.: `lucide-react`).
- Layout com **flex/grid + gap**; nunca margens soltas entre irmãos.

---

## 4. Layout / App shell

Mesmo layout de três colunas da spec original (seção 4): header fixo de 60px, sidebar de clientes (288px,
recolhível a 52px), chat central flexível, painel de debug escuro (392px, recolhível a 52px). Nenhuma mudança
estrutural — a diferença está em **de onde vêm os dados** que preenchem cada painel, não na disposição visual.

---

## 5. Arquitetura de dados & API

### 5.1 Serviços e portas

| Serviço        | Papel                                                                            | URL padrão (dev)             |
| -------------- | -------------------------------------------------------------------------------- | ---------------------------- |
| `ai-agent`     | API HTTP consumida pela UI (`src/api.py`)                                        | `http://localhost:8080`      |
| `workshop-mcp` | MCP remoto de oficinas/perícias (consumido só pelo agente, nunca direto pela UI) | `http://localhost:8000/mcp`  |
| `policy-mcp`   | MCP remoto de gestão de apólices (idem)                                          | `http://localhost:8001/mcp`  |
| MongoDB Atlas  | Fonte de dados (`customer_profile`, `policy_chunks`, `workshops`, memórias)      | — (acesso só via `ai-agent`) |

A UI **só fala com `ai-agent`**. `workshop-mcp` e `policy-mcp` são invisíveis para o frontend — são detalhes de
implementação do agente.

### 5.2 Endpoints já existentes (não alterar contrato)

**`GET /health`**
Ping de disponibilidade (verifica conexão com o Mongo). Resposta `200 {"status": "ok"}` ou `503` com detalhe do
erro. Usar para o indicador "● Agente online" do header (ver seção 6.1) — se o `/health` falhar, o pill deve
mudar para um estado de erro/offline (não especificado na spec original, que assumia sempre online).

**`POST /chat`**
Requisição:

```json
{
  "customer_id": "cust_1001",
  "message": "texto do cliente",
  "thread_id": "cust_1001_a1b2c3d4"
}
```

`thread_id` é opcional — se omitido, o backend gera um novo e o devolve na resposta. Resposta:

```json
{
  "thread_id": "cust_1001_a1b2c3d4",
  "response": "texto da resposta final do agente",
  "debug": {
    "long_term_facts": [ { "fact": "...", "recorded_at": "2026-06-30T12:00:00Z" } ],
    "new_fact_saved": { "fact": "...", "recorded_at": "..." } | null,
    "tool_calls_made": [
      { "tool_name": "vector_search_clausulas", "input": { "query": "...", "category": "auto" }, "output": [ ... ] }
    ]
  }
}
```

Usar apenas como fallback (ex.: ambiente sem suporte a streaming) — o fluxo principal do chat é via
`/chat/stream` (seção 5.3).

**`POST /chat/stream`** (SSE)
Mesmo corpo de requisição do `/chat`. Eventos `data:` emitidos em sequência:

1. `{"type": "start", "thread_id": "..."}` — sempre o primeiro evento; a UI deve persistir esse `thread_id` no
   estado do cliente ativo (ver seção 7) mesmo quando a requisição não informou um.
2. `{"type": "token", "content": "pedaço de texto"}` — zero ou mais eventos, um por pedaço da resposta final,
   na ordem gerada. Tool calls **não** geram eventos de token.
3. `{"type": "done", "response": "texto completo", "debug": {...}}` — último evento, mesmo formato de `debug`
   do `/chat`. Encerra o stream.
4. `{"type": "error", "detail": "mensagem"}` — em caso de falha (ex.: MCP fora do ar); encerra o stream sem
   `done`.

> Hoje **não existem** eventos de progresso por tool call (ex. "tool X começou/terminou") — só o evento `done`
> final carrega `tool_calls_made`. Ver seção 5.4 para o que isso implica no painel de debug.

### 5.3 Endpoints novos necessários (a implementar em `ai-agent/src/api.py`)

A spec original assumia uma lista de clientes hardcoded; para expor os clientes reais do MongoDB, dois
endpoints de leitura precisam ser adicionados. Ambos são leituras diretas em `customer_profile` — não passam
pelo grafo do agente, então não violam o "ponto de acoplamento único" descrito no CLAUDE.md para `agent.invoke`
(esse princípio vale para lógica de agente/tools, não para listagem read-only de perfis).

**`GET /clients`** (novo)
Lista os clientes disponíveis para o seletor da sidebar. Resposta:

```json
[
  {
    "customer_id": "cust_1001",
    "name": "Carlos Mendonça",
    "policies": [{ "policy_id": "POL-AUTO-9981", "type": "auto" }],
    "open_claims_count": 1,
    "contact_preference": "whatsapp"
  }
]
```

Implementação sugerida: projeção de `customer_profile` trazendo só os campos usados no `ClientCard` (evitar
devolver `claims`/`policies` completos aqui — isso vem no detalhe, endpoint abaixo).

**`GET /clients/{customer_id}`** (novo)
Perfil completo de um cliente — mesmo documento retornado por `find_one({"customer_id": ...}, {"_id": 0})` em
`load_memory` (`ai-agent/src/graph/nodes.py`). Resposta: o schema completo da seção 5.5. `404` se não existir.

Usado para popular o `ClientProfileDialog` (seção 6.5) sem depender do que já foi injetado no chat.

### 5.4 Implicação para o painel de debug ("em execução")

O critério "status em execução com pulse" da spec original **não é observável com o contrato atual**: o
backend só reporta tool calls já concluídas, no evento `done`. Duas opções, a escolher pelo time antes de
implementar a timeline "ao vivo":

1. **(Recomendado, menor escopo)** Tratar todas as tool calls do turno como já concluídas assim que o evento
   `done` chega — a timeline de debug é preenchida de uma vez, sem estado "em execução" real. O pulse/âmbar da
   spec de design vira só um estado visual possível do componente (usado, no máximo, enquanto o turno inteiro
   está em andamento — ver `ChatPanel`/indicador de digitação), não por tool call individual.
2. **(Fidelidade total ao design original)** Adicionar em `ai-agent/src/agent.astream` (`ai-agent/src/agent.py`)
   escuta a mais em `graph.astream_events` para os eventos `on_tool_start` / `on_tool_end`, emitindo novos
   tipos de evento SSE:
   - `{"type": "tool_start", "tool_name": str, "input": dict}`
   - `{"type": "tool_end", "tool_name": str, "output": any}`
     Isso é uma **mudança de backend**, fora do escopo puro de frontend — precisa ser priorizada à parte.

Esta spec segue com a **opção 1** como padrão (menor escopo, não requer mudança de backend); a opção 2 fica
documentada como extensão futura caso o time queira o efeito visual completo.

### 5.5 Schema real de `customer_profile` (fonte: `data/seed_customer_profiles.json`, `ai-agent/src/graph/nodes.py`)

```ts
interface Policy {
  policy_id: string; // "POL-AUTO-9981" | "POL-RES-3301"
  type: 'auto' | 'residencial';
  status: 'active' | 'pending';
  renewal_date: string; // "YYYY-MM-DD"
  vehicle?: string; // presente quando type === 'auto'
  address?: string; // presente quando type === 'residencial'
}

interface Claim {
  claim_id: string; // "CLM-4471"
  type: string; // "colisao" | "vazamento" | "roubo" | ... (texto livre por enquanto)
  status: string; // "em_analise" | "aprovado" | "pago" | ...
  opened_at: string; // "YYYY-MM-DD"
  description: string;
}

interface CustomerProfile {
  customer_id: string; // "cust_1001"
  name: string;
  cep: string; // usado por buscar_oficinas_proximas
  policies: Policy[]; // 0..N, tipos podem se repetir/misturar
  claims: Claim[]; // 0..N
  contact_preference: 'whatsapp' | 'email' | 'telefone';
}
```

Não existem no schema real: CPF, data de nascimento, cidade (só CEP), telefone, e-mail, score de crédito,
status de pagamento, valor de parcela, forma de pagamento, lista estruturada de coberturas com limites,
histórico textual de sinistros ou campo de observações do agente. Esses campos existiam apenas no mock da spec
original — ver seção 6.5 para como o modal de perfil deve se adaptar à ausência deles.

---

## 6. Componentes

### 6.1 `AppHeader`

Igual à spec original, com uma mudança: o pill "● Agente online" deve refletir o resultado real de `GET
/health`, checado ao carregar a aplicação e em polling leve (ex.: a cada 30s). Três estados possíveis:
`online` (verde, como antes), `offline`/`indisponível` (usar `--vz-muted` ou uma variante de alerta — não
definida na paleta original, escolher um cinza/vermelho discreto), `verificando` (estado inicial, antes da
primeira resposta do `/health`).

### 6.2 `ClientSidebar` / `ClientCard`

- A lista de clientes vem de `GET /clients` (seção 5.3), carregada uma vez ao montar a aplicação. Estados:
  `loading` (skeleton ou spinner simples no lugar da lista), `error` (mensagem curta + botão "tentar de novo"),
  `success` (lista de `ClientCard`).
- `ClientCard` não tem mais um único par ramo/motivo fixo — como um cliente pode ter várias apólices de tipos
  diferentes:
  - Mostrar um `Badge` por **tipo de apólice único** presente em `policies` (ex.: cliente com auto + residencial
    mostra dois badges `Auto` e `Residencial`).
  - Substituir o badge de "motivo" (que não existe mais) por um indicador de sinistros em aberto, se houver:
    `Badge` outline com `"{n} sinistro(s) em aberto"` quando `open_claims_count > 0`; omitir o badge se for 0.
  - Nº de apólice: se houver mais de uma, mostrar a primeira + sufixo `+N` (ex.: `POL-AUTO-7712 +1`); o
    detalhe completo fica no modal de perfil.

### 6.3 `ChatPanel` / `ChatBubble`

- Cabeçalho do chat: nome do cliente + subtítulo derivado de `policies` (ex.: `{n} apólice(s) ativa(s)` em vez
  do `headerSub` fixo da spec original) e canal preenchido a partir de `contact_preference` (mapear
  `whatsapp`→"WhatsApp", `email`→"E-mail", `telefone`→"Telefone" — não existe mais "Chat do app" como valor
  real).
- Campo de mensagem **deixa de ser estático**: `Input` controlado + botão de enviar habilitado, disparando o
  fluxo abaixo. Desabilitar input enquanto uma resposta está em andamento (usar o estado de digitação para
  isso, não um novo campo).
- **Fluxo de envio de mensagem:**
  1. Ao enviar, adicionar imediatamente uma `ChatBubble` `role: "user"` com o texto digitado (otimista, sem
     esperar o backend).
  2. Abrir a conexão SSE em `POST {VITE_API_BASE_URL}/chat/stream` com `{customer_id, message, thread_id}`
     (usar o `thread_id` já conhecido do cliente ativo, se existir).
  3. No evento `start`: gravar/atualizar o `thread_id` do cliente ativo no estado global (seção 7) — importante
     porque a primeira mensagem de uma conversa nova não tem `thread_id` ainda.
  4. Em cada evento `token`: concatenar o `content` numa bolha `role: "agent"` em construção (mostrar como texto
     progressivo, sem esperar o fim do turno) — substitui o indicador de "digitação" fixo da spec original por
     um streaming real; manter o indicador de três pontos apenas no intervalo entre o envio e o primeiro token
     recebido.
  5. No evento `done`: fechar a bolha em construção com o texto final (`response`), e repassar `debug` para o
     `DebugPanel` do cliente ativo (seção 6.4).
  6. No evento `error`: exibir a mensagem de erro como uma bolha de sistema discreta (não uma bolha do agente)
     e reabilitar o input.
- `chips` deixam de ser um campo estruturado da API — ou são removidos da bolha, ou (opcional, se o time quiser
  manter o efeito visual) extraídos client-side por regex simples sobre o texto da resposta para padrões
  conhecidos (ex.: `\bSIN-\d{4}-\d{2}\b`, `\bPOL-(AUTO|RES)-\d{4}\b`, `\bEND-\d{4}\b`). Tratar como
  "nice-to-have", não bloqueante para os critérios de aceitação.
- Histórico ao trocar de cliente: como não há endpoint de listagem/retomada de threads, cada cliente mantém, em
  memória do browser (Zustand, seção 7), o próprio `thread_id` e a lista de mensagens trocadas **durante a
  sessão atual da UI**. Recarregar a página reinicia o histórico visível (aceitável — a memória de curto prazo
  real continua no Mongo por `thread_id`, só não há hoje uma forma de "redescobrir" um `thread_id` antigo pela
  UI).

### 6.4 `DebugPanel` / `ToolCallCard`

- Fonte de dados: `debug.tool_calls_made` do evento `done` mais recente do cliente ativo. Substituir
  completamente o modelo mock `AgentAction` (campos `icon`, `status`, `desc`, `params: {k,v}[]`, `result`,
  `time`, `dur`) pelo shape real: `{tool_name: string, input: Record<string, unknown>, output: unknown}` (ver
  seção 7).
- Mapear `tool_name` → ícone e label amigável usando uma tabela fixa no frontend (não vem da API):

  | `tool_name`                   | Label sugerido                |
  | ----------------------------- | ----------------------------- |
  | `vector_search_clausulas`     | Busca de cláusulas            |
  | `buscar_oficinas_proximas`    | Busca de oficinas parceiras   |
  | `consultar_agenda_pericia`    | Consulta de agenda de perícia |
  | `agendar_pericia`             | Agendamento de perícia        |
  | `listar_agendamentos_cliente` | Consulta de agendamentos      |
  | `cancelar_agendamento`        | Cancelamento de agendamento   |
  | `alterar_agendamento`         | Alteração de agendamento      |
  | `listar_apolices_cliente`     | Consulta de apólices          |
  | `criar_apolice`               | Criação de apólice            |
  | `atualizar_apolice`           | Atualização de apólice        |

  Tool não mapeada (ex.: nova tool adicionada no futuro): usar `tool_name` cru como label, ícone genérico.

- Status: como definido na seção 5.4 opção 1, toda entrada chega já concluída (`status: "ok"` sempre) — o
  `Badge` "em execução" fica reservado como estado visual do componente para uso futuro (opção 2), não é
  exercitado com o contrato atual.
- `params`: serializar `input` (objeto arbitrário) como lista `chave: valor` para o bloco de código mono,
  formatando valores não-primitivos (`object`/`array`) com `JSON.stringify(v, null, 2)` truncado a um número
  razoável de linhas (ex.: 6) com reticências.
- `result`: serializar `output` da mesma forma que `params`; se `output` for uma lista longa (ex.:
  `vector_search_clausulas` pode retornar vários chunks), mostrar um resumo (`"3 cláusula(s) encontrada(s)"`)
  com opção de expandir para o JSON completo.
- **Timestamp/latência não existem na API hoje.** Remover os campos `time`/`dur` do rodapé do card, ou (mínimo
  esforço, só no frontend) marcar o timestamp de chegada do evento `done` no cliente como aproximação do
  "momento" da chamada — deixar claro na UI que é um valor aproximado (ex.: rotular "recebido às", não
  "executado às"). Latência por chamada individual não é recuperável sem a mudança de backend da seção 5.4
  opção 2 — remover essa métrica ou tratá-la como indisponível.
- Métricas de sessão: `Ferramentas` = `tool_calls_made.length` do turno mais recente (ou acumulado da sessão,
  a decidir — recomendado: acumulado de todos os turnos da conversa atual, somando os `tool_calls_made` de cada
  `done` recebido). `Latência` (soma): **remover** do painel de métricas, já que não há dado real de duração por
  chamada — não inventar um valor.
- Adicionar um bloco novo, ausente na spec original, para expor a memória de longo prazo real: lista de
  `long_term_facts` (fatos conhecidos sobre o cliente) e, quando presente, um destaque de `new_fact_saved` no
  turno atual — ambos vêm prontos no `debug`. Pode viver na mesma aba "Ações do agente" (seção separada abaixo
  da timeline) ou na aba "Logs brutos" (ver abaixo).
- Aba "Logs brutos": deixar de ser um placeholder e mostrar o `debug` cru (JSON formatado) do turno mais
  recente — é literalmente o dado que a API já devolve, sem necessidade de mock.

### 6.5 `ClientProfileDialog`

Reestruturar o corpo do modal para o schema real (seção 5.5), carregado via `GET /clients/{customer_id}` ao
abrir o modal (não reaproveitar só o que já veio pelo chat, para garantir dado atualizado — ex.: depois de uma
`atualizar_apolice`/`criar_apolice` bem-sucedida).

Seções revisadas:

1. **Cabeçalho:** avatar (iniciais) + nome + `customer_id` em mono (substitui "nº apólice · produto" fixo, já
   que agora pode haver N apólices de tipos diferentes).
2. **Dados de contato:** CEP, canal de preferência (`contact_preference`, com o mesmo mapeamento de rótulo da
   seção 6.3). **Remover** os campos que não existem no schema real: CPF, nascimento, cidade, telefone, e-mail,
   score, status de pagamento — não inventar esses dados nem preenchê-los com placeholder "N/D" que sugira que
   deveriam existir; simplesmente omitir a seção/linha.
3. **Apólices (lista, uma entrada por item de `policies`):** para cada apólice — nº (`policy_id`), tipo
   (`Badge` Auto/Residencial), status (`Badge`: `active` verde / `pending` âmbar), vigência/renovação
   (`renewal_date`), e o campo específico do tipo (`vehicle` ou `address`) com rótulo dinâmico
   (`bemLabel = type === 'auto' ? 'Veículo segurado' : 'Imóvel segurado'`, mesma lógica da spec original).
4. **Sinistros (lista, uma entrada por item de `claims`):** nº (`claim_id`), tipo, status (`Badge` colorido por
   status — `em_analise` âmbar, `aprovado`/`pago` verde, sem mapeamento definido para outros valores: usar
   cinza neutro como default), data de abertura (`opened_at`), descrição. Lista vazia → estado vazio "Nenhum
   sinistro registrado" (não uma string mock).
5. **Coberturas contratadas:** removido como lista estruturada (não existe fonte real por apólice/cliente).
   Substituir por um botão de ação **"Consultar cláusulas da apólice"** que, ao clicar, fecha o modal e envia
   ao chat uma mensagem pré-formatada (ex.: `"Quais são as coberturas da minha apólice {policy_id}?"`),
   reaproveitando o fluxo real de `vector_search_clausulas` em vez de duplicar dado em outro endpoint.
6. **Histórico de sinistros / Observações do agente:** removidos (não existem no schema). Se o time quiser
   manter uma seção de "observações", ela precisaria de um campo novo em `customer_profile` — fora do escopo
   desta spec (documentar como possível extensão futura, não implementar).

---

## 7. Modelos de dados (TypeScript)

Substitui integralmente a seção 6 da spec original.

```ts
type PolicyType = 'auto' | 'residencial';
type PolicyStatus = 'active' | 'pending';
type Role = 'user' | 'agent' | 'system'; // 'system' cobre a bolha de erro de stream

interface Policy {
  policy_id: string;
  type: PolicyType;
  status: PolicyStatus;
  renewal_date: string; // "YYYY-MM-DD"
  vehicle?: string;
  address?: string;
}

interface Claim {
  claim_id: string;
  type: string;
  status: string;
  opened_at: string;
  description: string;
}

interface CustomerProfile {
  customer_id: string;
  name: string;
  cep: string;
  policies: Policy[];
  claims: Claim[];
  contact_preference: 'whatsapp' | 'email' | 'telefone';
}

// GET /clients — versão resumida para a sidebar
interface ClientSummary {
  customer_id: string;
  name: string;
  policies: { policy_id: string; type: PolicyType }[];
  open_claims_count: number;
  contact_preference: 'whatsapp' | 'email' | 'telefone';
}

interface ChatMessage {
  id: string; // gerado client-side (uuid), não vem da API
  role: Role;
  text: string;
  time: string; // "08:47", derivado de Date.now() no momento de criação (não vem da API)
  pending?: boolean; // true enquanto a bolha do agente ainda está recebendo tokens
}

// Uma entrada real de debug.tool_calls_made
interface ToolCall {
  tool_name: string;
  input: Record<string, unknown>;
  output: unknown;
}

interface TurnDebug {
  long_term_facts: { fact: string; recorded_at: string }[];
  new_fact_saved: { fact: string; recorded_at: string } | null;
  tool_calls_made: ToolCall[];
}

// Estado de conversa por cliente, mantido no frontend (não persiste entre reloads)
interface ClientConversation {
  thread_id: string | null; // null até o primeiro evento "start"
  messages: ChatMessage[];
  lastDebug: TurnDebug | null;
  toolCallHistory: ToolCall[]; // acumulado de todos os turnos, para a métrica "Ferramentas"
}
```

### Métricas derivadas (no seletor do cliente ativo)

- `toolCount = conversation.toolCallHistory.length`
- `bemLabel(policy) = policy.type === 'auto' ? 'Veículo segurado' : 'Imóvel segurado'`
- ~~`totalLat`~~ — removida (sem dado real de latência, ver seção 6.4).

---

## 8. Estado da aplicação (Zustand)

Substitui a seção 7 da spec original.

```ts
interface UIState {
  // navegação/layout (igual à spec original)
  selectedClientId: string | null;
  modalOpen: boolean;
  leftMin: boolean;
  rightMin: boolean;

  // dados carregados da API
  clients: ClientSummary[];
  clientsStatus: 'idle' | 'loading' | 'error' | 'success';
  clientProfile: Record<string, CustomerProfile>; // cache por customer_id, populado ao abrir o modal
  health: 'checking' | 'online' | 'offline';

  // conversas, por cliente
  conversations: Record<string, ClientConversation>;

  // ações
  loadClients(): Promise<void>;
  selectClient(customerId: string): void;
  toggleLeft(): void;
  toggleRight(): void;
  openModal(): Promise<void>; // dispara GET /clients/{id} se ainda não estiver em cache
  closeModal(): void;
  sendMessage(customerId: string, text: string): Promise<void>; // abre o SSE e vai atualizando `conversations`
}
```

Trocar de cliente (`selectClient`) atualiza chat, debug e o conteúdo do modal simultaneamente, todos derivados
de `conversations[selectedClientId]` e `clientProfile[selectedClientId]` — mesmo princípio da spec original,
adaptado para dados assíncronos.

---

## 9. Cenários de demonstração

Diferente da spec original (que fixava transcrições completas), aqui a resposta do agente é sempre gerada ao
vivo — os "cenários" são **roteiros de mensagens sugeridas**, não texto esperado literal. Basear-se nos 4
clientes reais do seed (`data/seed_customer_profiles.json`):

| Cliente            | `customer_id` | Apólices                                              | Sinistros                        | Roteiro sugerido                                                                                                                                                                             |
| ------------------ | ------------- | ----------------------------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Carlos Mendonça    | `cust_1001`   | Auto (`POL-AUTO-9981`, Honda Civic 2022)              | 1 em análise (colisão)           | "Bati o carro no estacionamento de um shopping, o que eu faço?" — dispara `vector_search_clausulas` + reconhecimento do sinistro `CLM-4471` já aberto.                                       |
| Ana Paula Ferreira | `cust_1002`   | Auto (`POL-AUTO-7712`) + Residencial (`POL-RES-3301`) | 1 em análise (vazamento)         | "Minha caixa d'água estourou e molhou a sala, isso está coberto?" — cobertura de danos por água + sinistro `CLM-5528` já aberto. Bom cenário para mostrar o card com dois badges de apólice. |
| Roberto Alves      | `cust_1003`   | Auto (`POL-AUTO-5543`, VW Gol 2020)                   | 2 (roubo aprovado, colisão paga) | "Troquei de carro, agora tenho um Jeep Compass 2024" — dispara o fluxo pró-ativo de `atualizar_apolice`. Bom cenário para o modal mostrar histórico de 2 sinistros com status diferentes.    |
| Marina Torres      | `cust_1004`   | Auto (`POL-AUTO-6640`, Ford Fiesta 2019)              | Nenhum                           | "Preciso de uma oficina perto de mim para revisar o carro" — dispara `buscar_oficinas_proximas` usando o CEP do perfil. Bom cenário para mostrar o estado vazio de sinistros no modal.       |

Esses roteiros existem só para orientar a demo (o que digitar); não devem ser codificados como respostas fixas
em lugar nenhum do frontend.

---

## 10. Interações & animações

Mantém a seção 8 da spec original (transições de seleção, minimizar/expandir, `@keyframes blink`/`pulse`,
modal com `AnimatePresence`, acessibilidade), com dois ajustes:

- O indicador de digitação (3 pontos) é exibido apenas entre o envio da mensagem e a chegada do primeiro evento
  `token` — depois disso, o texto real vai aparecendo progressivamente (efeito "streaming"), substituindo os 3
  pontos.
- O pulse "em execução" do `ToolCallCard`, por ora sem uso real (seção 6.4), permanece implementado no
  componente mas não é acionado por nenhum dado da API atual — deixar o componente pronto para o dia em que a
  opção 2 da seção 5.4 for implementada.

---

## 11. Estrutura de arquivos sugerida

```
src/
  lib/
    api.ts                   // fetch de GET /health, GET /clients, GET /clients/{id}, POST /chat
    sse.ts                   // parser de POST /chat/stream (fetch-event-source ou equivalente)
    format.ts                 // bemLabel, labels de tool_name, mapeamento de contact_preference
  store/uiStore.ts            // Zustand (seção 8)
  components/
    AppHeader.tsx
    ClientSidebar.tsx
    ClientCard.tsx
    ChatPanel.tsx
    ChatBubble.tsx
    TypingIndicator.tsx
    DebugPanel.tsx
    ToolCallCard.tsx
    LongTermFactsPanel.tsx    // novo — lista de long_term_facts / new_fact_saved
    ClientProfileDialog.tsx
    CollapsedRail.tsx
  ui/                          // componentes shadcn/ui gerados
  App.tsx
  index.css                    // tokens/variáveis + fontes (seção 3, sem alteração)
```

---

## 12. Configuração necessária

- `VITE_API_BASE_URL` no `.env` do frontend, apontando para `ai-agent` (`http://localhost:8080` em dev).
- **CORS**: `ai-agent/src/api.py` hoje não tem `CORSMiddleware` configurado. Como o frontend React roda em uma
  origem diferente (porta do Vite, ex. `5173`), é necessário adicionar
  `app.add_middleware(CORSMiddleware, allow_origins=[...], allow_methods=["*"], allow_headers=["*"])` no
  `ai-agent`, liberando pelo menos a origem do dev server. Isso é uma mudança de backend fora do escopo do
  frontend, mas é um bloqueador direto — sem ela, toda chamada da UI a `/health`, `/chat` e `/chat/stream`
  falha por política de CORS do browser.
- Serviços que precisam estar de pé para a demo funcionar: MongoDB Atlas seedado, `workshop-mcp`, `policy-mcp`,
  `ai-agent` (com os dois novos endpoints da seção 5.3 e o CORS acima).

---

## 13. Critérios de aceitação

1. Três colunas visíveis em tela cheia; apenas as áreas de conteúdo rolam — igual à spec original.
2. Selecionar um cliente carrega seu perfil resumido (sidebar) e, ao abrir o modal, seu perfil completo via
   `GET /clients/{id}` — sem dados hardcoded no componente.
3. Painéis de clientes e de debug minimizam/expandem para trilhas de 52px — igual à spec original.
4. Enviar uma mensagem no chat efetivamente chama `POST /chat/stream`, exibe tokens conforme chegam, e finaliza
   a bolha com o `response` do evento `done`.
5. Modal de perfil mostra apenas dados existentes no schema real (seção 5.5); nenhum campo do mock antigo (CPF,
   score, coberturas com limite, etc.) aparece com valor inventado ou placeholder.
6. Painel de debug reflete `tool_calls_made`, `long_term_facts` e `new_fact_saved` reais do turno mais recente,
   com nomes de tool mapeados para labels amigáveis (tabela da seção 6.4).
7. Indicador de "● Agente online" reflete o resultado real de `GET /health`, com um estado de erro visível
   quando o backend está indisponível.
8. Nenhuma chamada direta a MongoDB nem a `workshop-mcp`/`policy-mcp` a partir do frontend — tudo passa por
   `ai-agent`.
9. Paleta, tipografia e formas conforme a seção 3 da spec original (sem alterações).
10. Componentes de biblioteca reutilizados onde indicado (seção 2); CSS manual restrito a layout/bolhas/timeline
    — igual à spec original.
