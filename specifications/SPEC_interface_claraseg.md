# SPEC — Interface do Agente de IA · Vivaz Seguros

Especificação de implementação para reconstruir a interface de demonstração do agente de IA em **React**. O documento é auto-suficiente: um agente de IA deve conseguir implementar a UI completa a partir daqui, **reutilizando componentes prontos de bibliotecas** sempre que possível.

---

## 1. Visão geral

Painel de **demonstração** de um agente de IA para uma seguradora (ramos Auto e Residencial). Uma única tela (app shell full-height) dividida em três colunas:

1. **Seleção de cliente** (esquerda) — lista de perfis fictícios para conduzir a demo. Recolhível.
2. **Chat** (centro) — conversa entre cliente e agente, com indicador de digitação e cabeçalho do cliente ativo.
3. **Debug / Ações do agente** (direita, tema escuro) — timeline das _tool calls_ executadas pelo agente, com parâmetros, resultado, timestamp e latência. Recolhível.

Recursos adicionais:

- **Modal de perfil completo** do cliente selecionado.
- **Minimizar** os painéis lateral e de debug (viram trilhas verticais estreitas).
- Idioma: **Português (BR)**. Conteúdo estático/roteirizado (mock), sem backend.

Cenários pré-carregados (1 por cliente): dúvida de cobertura, aviso de sinistro, atualização de apólice, dúvida sobre franquia.

---

## 2. Stack recomendada

| Camada           | Escolha recomendada              | Alternativas                   |
| ---------------- | -------------------------------- | ------------------------------ |
| Framework        | **React 18 + Vite + TypeScript** | Next.js (App Router)           |
| Biblioteca de UI | **shadcn/ui** (Radix + Tailwind) | MUI, Chakra UI, Mantine        |
| Estilização      | **Tailwind CSS**                 | CSS Modules, styled-components |
| Ícones           | **lucide-react**                 | react-icons, phosphor-react    |
| Animação         | **framer-motion**                | react-transition-group         |
| Estado           | **Zustand** (store leve)         | React Context + useReducer     |
| Datas/format     | **dayjs**                        | date-fns                       |

> **Regra do agente implementador:** priorize componentes prontos. Não escreva do zero um `Dialog`, `Avatar`, `Badge`, `ScrollArea`, `Tabs`, `Button`, `Tooltip` ou `Separator` — use os equivalentes de **shadcn/ui** (ou da lib escolhida). Escreva CSS manual apenas para o layout de 3 colunas, as bolhas de chat e a timeline de debug.

### Mapeamento para componentes prontos (shadcn/ui)

| Elemento da UI                           | Componente pronto                             |
| ---------------------------------------- | --------------------------------------------- |
| Cartão de cliente / cabeçalhos           | `Card`, `Avatar`                              |
| Tags de ramo / status / "concluído"      | `Badge`                                       |
| Botões (enviar, minimizar, ver perfil)   | `Button` (variantes `default`/`ghost`/`icon`) |
| Modal de perfil                          | `Dialog`                                      |
| Abas "Ações do agente" / "Logs brutos"   | `Tabs`                                        |
| Listas com scroll (clientes, chat, logs) | `ScrollArea`                                  |
| Divisores                                | `Separator`                                   |
| Dicas nos botões de minimizar            | `Tooltip`                                     |
| Campo de mensagem                        | `Input`                                       |

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

```
┌───────────────────────────────────────────────────────────────┐
│  HEADER  (60px, full width)                                     │
│  [logo V] Vivaz Seguros / subtítulo        [online] [modelo]    │
├──────────┬───────────────────────────────┬────────────────────┤
│ CLIENTES │           CHAT                │   DEBUG (escuro)    │
│ 288px    │           flex:1              │   392px             │
│ (recol-  │  header do cliente            │  tabs + métricas    │
│  hível → │  lista de mensagens (scroll)  │  timeline (scroll)  │
│  52px)   │  campo de mensagem            │  (recolhível→52px)  │
└──────────┴───────────────────────────────┴────────────────────┘
```

- Container raiz: `height: 100vh; display:flex; flex-direction:column; overflow:hidden`.
- Linha central: `flex:1; display:flex; min-height:0`.
- Cada painel de scroll: `flex:1; overflow-y:auto; min-height:0`.

### 4.1 Header (topo)

- Esquerda: quadrado com "V" (fundo acento, `Bricolage`), wordmark **Vivaz Seguros** + subtítulo `Agente de IA · Ambiente de demonstração`.
- Direita: pill "● Agente online" (verde) + chip mono `gpt-agent · v2.4`.

---

## 5. Componentes

### 5.1 `ClientSidebar` (coluna esquerda)

- Título "SELECIONE O CLIENTE" + descrição curta + **botão minimizar** (`«`).
- Lista de `ClientCard` (usar `Card` + `Avatar` + `Badge`).
- Rodapé: bloco "Modo apresentação · 4 cenários pré-carregados".
- **Estado recolhido:** trilha de 52px com botão expandir (`»`), rótulo vertical "CLIENTES" (`writing-mode: vertical-rl`) e o avatar (iniciais) do cliente ativo.

#### `ClientCard`

Props: `client`, `selected`, `onSelect`.

- Avatar (iniciais) — acento quando selecionado, cinza quente caso contrário.
- Nome (600) + nº de apólice (mono, `muted`).
- Selecionado: fundo branco, borda de acento `1.5px`, sombra suave, ponto de acento à direita.
- Linha de tags: `Badge` do ramo (`Auto`/`Residencial`) + `Badge` outline do motivo.

### 5.2 `ChatPanel` (centro)

- **Cabeçalho:** avatar + nome + subtítulo (`Apólice … · desde ANO`); à direita pill do canal (`WhatsApp`/`Chat do app`) + **botão `Ver perfil completo`** (CTA acento, abre o `Dialog`).
- **Corpo:** `ScrollArea` com:
  - Separador de dia centralizado (pill): `Hoje · 08h47`.
  - Lista de `ChatBubble`.
  - **Indicador de digitação** ao final: avatar "V" + três pontos com animação `blink` alternada.
- **Rodapé:** campo `Input` desabilitado/estático "Digite uma mensagem para o agente…" + botão de enviar (ícone, acento). Estático na demo.

#### `ChatBubble`

Props: `role` (`"user" | "agent"`), `text`, `time`, `chips?`.

- **agent:** alinhado à esquerda, com avatar "V" (acento) na base; bolha `--vz-surface`, texto `--vz-ink`, canto inferior-esquerdo reto.
- **user:** alinhado à direita, bolha acento, texto branco, canto inferior-direito reto; sem avatar.
- `text` respeita `white-space: pre-wrap` (mensagens podem ter quebras).
- `chips` (opcional): destaques ao final da bolha do agente (ex.: `Protocolo SIN-4471-25`, `Guincho a caminho`) — pills de acento suave.
- `time` (ex.: `08:47`) em fonte pequena; `muted` para agente, branco translúcido para usuário.
- `max-width: 82%` da coluna.

### 5.3 `DebugPanel` (direita, escuro)

- `Tabs` no topo: **Ações do agente** (ativa) · **Logs brutos** + **botão minimizar** (`»`).
- Faixa de métricas da sessão (3 blocos, mono): `Sessão` (id) · `Ferramentas` (nº de chamadas) · `Latência` (soma, em verde).
- **Timeline vertical** (`ScrollArea`): linha vertical + "dots" por item; cada item é um `ToolCallCard`.
- **Estado recolhido:** trilha de 52px com botão expandir, rótulo vertical "DEBUG · AÇÕES" e um ponto de acento.

#### `ToolCallCard`

Props: `action` (ver modelo `AgentAction`).

- Cabeçalho: ícone (emoji ou `lucide`) + nome da tool (mono, ex.: `consultar_apolice`) + `Badge` de status (`concluído` verde / `em execução` âmbar com pulse).
- Corpo: descrição curta; bloco de código escuro com os `params` (`chave: valor` em mono, valores em verde-claro); linha de resultado prefixada por `↳`; rodapé com timestamp (esq.) e duração (dir.), ambos mono.
- "Dot" na timeline: acento (ou âmbar com halo pulsante quando em execução), com borda da cor do fundo do painel.

### 5.4 `ClientProfileDialog` (modal)

Usar `Dialog` (shadcn/Radix). Abre pelo botão "Ver perfil completo".

- **Cabeçalho** (faixa acento): avatar grande, nome (`Bricolage`), linha mono `nº apólice · produto`, botão fechar (`✕`).
- **Corpo** (`ScrollArea`), seções:
  1. **3 cards de resumo:** Status de pagamento (verde) · Score interno · Cliente desde.
  2. **Dados pessoais** (lista chave/valor): CPF, Nascimento, Cidade, Telefone, E-mail.
  3. **Apólice:** Número, Produto, Vigência, Parcela (+ forma de pagamento), Bem segurado (veículo **ou** imóvel — label dinâmico por ramo).
  4. **Coberturas contratadas:** lista `✓ nome … limite` (mono para o limite).
  5. **Dois cards:** Histórico de sinistros · Observações do agente.
- Overlay escuro com `backdrop-blur`; fechar por clique fora ou no `✕` (Radix já cobre `Esc` e trap de foco).

---

## 6. Modelos de dados (TypeScript)

```ts
type Ramo = 'Auto' | 'Residencial';
type Role = 'user' | 'agent';
type ActionStatus = 'ok' | 'run'; // concluído | em execução

interface ChatMessage {
  role: Role;
  text: string;
  time: string; // "08:47"
  chips?: string[]; // destaques na bolha do agente
}

interface AgentAction {
  name: string; // "consultar_apolice"
  icon: string; // emoji ou nome de ícone lucide
  status: ActionStatus;
  desc: string; // descrição curta
  params: { k: string; v: string }[]; // pares chave/valor (v já formatado)
  result: string; // "" quando ainda em execução
  time: string; // "08:48:11"
  dur: string; // "340 ms" | "—"
}

interface ClientProfile {
  cpf: string;
  nascimento: string;
  cidade: string;
  telefone: string;
  email: string;
  clienteDesde: string;
  score: string;
  statusPag: string;
  produto: string;
  vigencia: string;
  parcela: string;
  forma: string;
  veiculo: string; // descrição do bem (veículo OU imóvel)
  coberturas: [string, string][]; // [nome, limite]
  sinistros: string;
  obs: string;
}

interface Client {
  id: string;
  name: string;
  initials: string;
  apolice: string; // "AUTO-88·214·507"
  ramo: Ramo;
  motivo: string; // "Aviso de sinistro"
  headerSub: string; // "Apólice Auto Total · desde 2021"
  canal: string; // "WhatsApp" | "Chat do app"
  dia: string; // "Hoje · 08h47"
  sessionId: string; // "ses_9f2a·c41"
  messages: ChatMessage[];
  logs: AgentAction[];
  profile: ClientProfile;
}
```

### Métricas derivadas (no seletor do cliente ativo)

- `toolCount = client.logs.length`
- `totalLat = soma de parseInt(log.dur) + " ms"`
- `bemLabel = ramo === "Auto" ? "Veículo segurado" : "Imóvel segurado"`

---

## 7. Estado da aplicação (Zustand ou Context)

```ts
interface UIState {
  selectedIndex: number; // cliente ativo (default 0)
  modalOpen: boolean; // dialog de perfil
  leftMin: boolean; // painel de clientes recolhido
  rightMin: boolean; // painel de debug recolhido
  select(i: number): void;
  toggleLeft(): void;
  toggleRight(): void;
  openModal(): void;
  closeModal(): void;
}
```

Trocar de cliente atualiza chat, debug e o conteúdo do modal simultaneamente (tudo deriva de `clients[selectedIndex]`).

---

## 8. Interações & animações

- **Seleção de cliente:** transição de borda/sombra/fundo (`transition: all .15s`).
- **Minimizar/expandir painéis:** animar largura (framer-motion `layout` ou transição de `width`). Trilha recolhida = 52px.
- **Indicador de digitação:** 3 pontos, `@keyframes blink` (opacity .2→1), delays `0 / .2s / .4s`.
- **Status "em execução":** `Badge` âmbar + "dot" com halo, `@keyframes pulse` (opacity .35→1, 1.4s infinite).
- **Modal:** fade + leve scale-in (framer-motion `AnimatePresence`); overlay com blur; fechar por overlay/`✕`/`Esc`.
- Acessibilidade: botões-ícone com `aria-label`/`Tooltip`; `Dialog` do Radix já entrega foco preso e `role` corretos.

---

## 9. Dados de exemplo (mock — 4 clientes)

Popular `clients` com os 4 perfis abaixo. Reproduzir integralmente os `messages` e `logs` para a demo ficar realista.

### Cliente 1 — Marina Alves · Auto · Aviso de sinistro

- apolice `AUTO-88·214·507` · headerSub `Apólice Auto Total · desde 2021` · canal `WhatsApp` · dia `Hoje · 08h47` · sessionId `ses_9f2a·c41`.
- **Chat:** cliente relata engavetamento na Marginal → agente confere bem-estar → localiza apólice Auto Total (cobre colisão) → confirma que carro não roda → registra sinistro, informa franquia **R$ 2.150,00**, aciona guincho (chips `Protocolo SIN-4471-25`, `Guincho a caminho`).
- **Logs:** `identificar_cliente` → `consultar_apolice` → `verificar_cobertura(colisao)` → `calcular_franquia` (R$ 2.150) → `abrir_sinistro` (SIN-4471-25, em_analise) → `acionar_assistencia_24h` (**em execução**).
- **profile:** CPF `327.•••.•••-04`, nasc. `14/03/1989 · 37 anos`, São Paulo·SP, tel `+55 11 9•••• 3021`, `marina.alves@email.com`, cliente desde Mar/2021, score "Bom pagador", status "Em dia", produto Auto Total, vigência `03/2025 — 03/2026`, parcela `R$ 289,90 /mês` (Cartão de crédito), veículo `Honda Civic EXL 2020 · SP-JKL2C10 · FIPE R$ 92.000`. Coberturas: Colisão/capotagem R$ 92.000; Roubo e furto R$ 92.000; Danos a terceiros R$ 100.000; Assistência 24h Ilimitada; Carro reserva 15 dias. Sinistros: "1 sinistro anterior (2022) · pequeno reparo". Obs: "Cliente prefere WhatsApp. Possui 2 veículos no CPF."

### Cliente 2 — Rafael Costa · Residencial · Dúvida de cobertura

- apolice `RES-70·118·902` · headerSub `Residencial Confort · desde 2023` · canal `Chat do app` · dia `Hoje · 14h12` · sessionId `ses_3b7d·e08`.
- **Chat:** vazamento danificou piso e forro → agente confirma cobertura **Danos por Água** → limite **R$ 30.000** e franquia **R$ 450** (chips) → oferece abrir aviso com perito.
- **Logs:** `identificar_cliente` → `consultar_apolice` → `verificar_cobertura(danos_por_agua)` → `consultar_limite` (R$ 30.000 / R$ 450). Todos `concluído`.
- **profile:** CPF `518.•••.•••-77`, nasc. `02/09/1985 · 40 anos`, Campinas·SP, tel `+55 19 9•••• 5510`, cliente desde Jan/2023, score "Excelente", produto Residencial Confort, vigência `01/2026 — 01/2027`, parcela `R$ 132,50 /mês` (Débito automático), imóvel `Casa · Rua das Acácias, 340 · 120 m² · alvenaria`. Coberturas: Incêndio/explosão R$ 250.000; Danos por água R$ 30.000; Danos elétricos R$ 15.000; Roubo de bens R$ 20.000; Resp. civil familiar R$ 50.000; Assistência residencial Ilimitada. Sinistros: "Sem sinistros registrados". Obs: "Imóvel próprio, sem financiamento."

### Cliente 3 — Juliana Menezes · Auto · Atualização de apólice

- apolice `AUTO-42·905·310` · headerSub `Auto Essencial · desde 2022` · canal `WhatsApp` · dia `Hoje · 10h05` · sessionId `ses_6c1e·a77`.
- **Chat:** trocou de carro → informa Jeep Compass 2024, placa RGT2B45 → agente cota FIPE, recalcula prêmio (**R$ 189,90 → R$ 236,40**, chips) → emite endosso `END-2210`.
- **Logs:** `identificar_cliente` → `consultar_apolice` (veículo antigo Onix 2019) → `consultar_fipe` (R$ 158.400) → `recalcular_premio` → `atualizar_veiculo` → `emitir_endosso` (END-2210). Todos `concluído`.
- **profile:** CPF `901.•••.•••-33`, nasc. `27/06/1993 · 32 anos`, Rio de Janeiro·RJ, cliente desde Ago/2022, score "Bom pagador", produto Auto Essencial, vigência `08/2025 — 08/2026`, parcela `R$ 236,40 /mês` (Cartão), veículo `Jeep Compass 2024 · RJ-RGT2B45 · FIPE R$ 158.400`. Coberturas: Colisão/capotagem R$ 158.400; Roubo e furto R$ 158.400; Danos a terceiros R$ 80.000; Assistência 24h Ilimitada. Sinistros: "Sem sinistros". Obs: "Endosso de troca de veículo emitido hoje (END-2210)."

### Cliente 4 — Bruno Ferreira · Residencial · Dúvida sobre franquia

- apolice `RES-19·640·775` · headerSub `Residencial Plus · desde 2020` · canal `Chat do app` · dia `Hoje · 19h33` · sessionId `ses_8a4f·d19`.
- **Chat:** pergunta sobre franquia em caso de furto → agente informa **Roubo e Furto Qualificado sem franquia**, limite **R$ 25.000**, furto simples excluído (chips `Sem franquia`, `Limite R$ 25.000`).
- **Logs:** `identificar_cliente` → `consultar_apolice` → `consultar_franquia` (R$ 0 / isenta) → `consultar_limite` (R$ 25.000, furto_simples excluído). Todos `concluído`.
- **profile:** CPF `146.•••.•••-58`, nasc. `11/12/1978 · 47 anos`, Belo Horizonte·MG, cliente desde Nov/2020, score "Excelente", produto Residencial Plus, vigência `11/2025 — 11/2026`, parcela `R$ 178,00 /mês` (Débito automático), imóvel `Casa · Alameda dos Ipês, 88 · 210 m² · 2 pavimentos`. Coberturas: Incêndio/explosão R$ 400.000; Roubo e furto qualificado R$ 25.000; Danos por água R$ 40.000; Danos elétricos R$ 25.000; Quebra de vidros R$ 8.000; Resp. civil familiar R$ 80.000; Assistência residencial Ilimitada. Sinistros: "1 sinistro anterior (2021) · danos elétricos". Obs: "Cliente antigo, 6 anos de relacionamento. Sem inadimplência."

---

## 10. Estrutura de arquivos sugerida

```
src/
  data/clients.ts            // array Client[] (mock da seção 9)
  store/uiStore.ts           // Zustand (seção 7)
  lib/format.ts              // helpers (soma de latência, bemLabel)
  components/
    AppHeader.tsx
    ClientSidebar.tsx
    ClientCard.tsx
    ChatPanel.tsx
    ChatBubble.tsx
    TypingIndicator.tsx
    DebugPanel.tsx
    ToolCallCard.tsx
    ClientProfileDialog.tsx
    CollapsedRail.tsx        // trilha reutilizável (esquerda/direita)
  ui/                        // componentes shadcn/ui gerados
  App.tsx
  index.css                  // tokens/variáveis + fontes
```

---

## 11. Critérios de aceitação

1. Três colunas visíveis em tela cheia; apenas as áreas de conteúdo rolam (header e campos fixos).
2. Selecionar um cliente atualiza **chat, debug e modal** de forma coerente.
3. Painéis de clientes e de debug **minimizam/expandem** para trilhas de 52px com rótulo vertical.
4. Modal de perfil abre pelo botão "Ver perfil completo", fecha por overlay/`✕`/`Esc`, e mostra todas as seções da 5.4.
5. Debug mostra as tool calls com status (`concluído`/`em execução` com pulse), params, resultado, timestamp e latência.
6. Indicador de digitação animado ao final do chat; status "em execução" pulsando na timeline.
7. Paleta, tipografia e formas conforme a seção 3.
8. Componentes de biblioteca reutilizados onde indicado (seção 2); CSS manual restrito a layout/bolhas/timeline.
9. Sem dependência de backend — tudo a partir do mock.
