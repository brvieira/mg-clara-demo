# SPEC.md — Interface ClaraSeg (Streamlit)

## 1. Visão geral

Interface de chat simples em Streamlit que permite simular uma conversa entre um segurado e o agente ClaraSeg, com seleção manual de cliente (simulando login) e visibilidade de qual sessão/thread está ativa — para deixar claro durante a demo quando uma nova "conversa" está começando, o que é importante para demonstrar a diferença entre memória de curto e longo prazo.

Esta interface é uma ferramenta de apresentação para pre-sales, não um produto polido. Priorizar clareza visual do que está acontecendo (qual cliente, qual sessão, o que foi recuperado da memória) sobre estética refinada — a interface deve ajudar a "narrar" a arquitetura durante a apresentação ao vivo.

## 2. Stack técnica

- **Framework:** Streamlit
- **Dependência do backend:** importa diretamente a função `invoke()` do módulo `src/agent.py` (ver SPEC.md do agente) — não há API REST intermediária, é tudo um único processo Python para simplificar a demo.
- **Gerenciamento de estado de sessão:** `st.session_state`

## 3. Estrutura de diretórios proposta

```
claraseg/
├── app.py                      # ponto de entrada do Streamlit
├── ui/
│   ├── __init__.py
│   ├── sidebar.py              # seleção de cliente, controle de sessão/thread
│   ├── chat.py                 # renderização do histórico de chat e input
│   └── debug_panel.py          # painel opcional mostrando memória recuperada (ver seção 6)
```

## 4. Layout da aplicação

### 4.1 Sidebar (coluna lateral)

- **Seletor de cliente:** dropdown com os 2-3 clientes fictícios do seed (`customer_profile`). Ao trocar de cliente, a conversa atual é encerrada e uma nova sessão começa.
- **Indicador de sessão atual:** mostra o `thread_id` ativo (abreviado, ex: `cust_1001_a3f9...`) para que durante a apresentação seja possível apontar "esta é a sessão atual".
- **Botão "Nova conversa":** gera um novo `thread_id` para o mesmo `customer_id`, mantendo o cliente mas começando uma sessão zerada — este é o botão que vai ser usado ao vivo para demonstrar que a memória de curto prazo NÃO atravessa esse botão, mas a de longo prazo SIM.
- **Botão "Resetar dados de demo":** opcional, restaura o estado inicial dos dados de seed (útil se a demo for repetida ou ensaiada várias vezes antes da apresentação real).

### 4.2 Área principal (chat)

- Histórico de mensagens renderizado com `st.chat_message` (papéis "user" e "assistant").
- Campo de input fixo na parte inferior com `st.chat_input`.
- Ao enviar mensagem: chama `agent.invoke(thread_id, customer_id, message)`, exibe um spinner enquanto processa, renderiza a resposta.

### 4.3 Painel de debug/transparência (opcional, mas recomendado para a apresentação)

Um expander (`st.expander`, fechado por padrão, abrir durante a demo no momento certo) mostrando, para a última interação:

- **Fatos de longo prazo recuperados** (o que veio do `MongoDBStore` para este cliente).
- **Cláusulas recuperadas via vector search** (com o texto da cláusula e, se possível, o score de similaridade).
- **Novo fato gravado nesta interação**, se houver.

Justificativa de design: isso transforma a demo de uma caixa-preta ("o agente respondeu certo, confia") em uma demonstração explícita da arquitetura de memória — que é exatamente o que o exercício técnico pede para ser explicado. Recomenda-se abrir esse painel no momento em que a apresentação chega na explicação de "como a memória funciona por baixo dos panos".

## 5. Fluxo de interação esperado na demo

1. Apresentador seleciona o cliente "Cliente A" na sidebar.
2. Inicia uma conversa perguntando sobre cobertura — demonstra vector search.
3. Faz uma segunda pergunta que depende do contexto da primeira (ex: "e isso cobre o carro que eu disse antes?") — demonstra memória de curto prazo dentro da mesma sessão.
4. Clica em "Nova conversa" (gera novo thread_id, mesmo cliente).
5. Pergunta algo que só faz sentido se o agente lembrar de um fato mencionado anteriormente em outra sessão (ex: "qual o status do meu sinistro mais recente?" ou um fato que foi gravado como long_term_memory em uma demo anterior) — demonstra memória de longo prazo persistindo entre sessões diferentes.
6. Abre o painel de debug para mostrar exatamente o que foi recuperado do MongoDB em cada uma dessas etapas.

## 6. Estado de sessão (`st.session_state`)

```python
st.session_state.customer_id        # cliente selecionado atualmente
st.session_state.thread_id          # sessão/conversa atual
st.session_state.chat_history       # lista de mensagens exibidas na tela (espelha o que está no checkpointer, mas mantido localmente para renderização rápida sem reconsultar o Mongo a cada rerender)
st.session_state.last_debug_info    # último resultado de memória recuperada, para o painel de debug
```

Nota de implementação: o histórico "oficial" da conversa vive no MongoDB via checkpointer — o `chat_history` em `session_state` é só uma cópia para renderização, e deve ser reconstruído a partir do backend (não recriado do zero) sempre que o `thread_id` mudar, para garantir que a UI nunca diverja do que está persistido.

## 7. Tratamento de erros visível na demo

- Se a conexão com o MongoDB falhar, exibir mensagem clara na interface (`st.error`) em vez de stack trace — importante para não quebrar a apresentação visualmente diante dos avaliadores.
- Se o LLM não responder dentro de um tempo razoável, exibir timeout amigável.
- Validar que o cliente selecionado tem ao menos uma apólice antes de permitir perguntas (evitar estado vazio confuso durante a demo ao vivo).

## 8. Fora de escopo

- Autenticação real (login/senha) — seleção de cliente é só um dropdown.
- Responsividade mobile — a demo é apresentada em desktop/projetor.
- Múltiplos idiomas — interface e respostas em português apenas.
- Persistência de preferências de UI entre sessões do navegador.

## 9. Checklist pré-apresentação

1. Rodar a aplicação localmente e testar o fluxo completo da seção 5 ao menos uma vez antes da apresentação real.
2. Confirmar que os dados de seed estão carregados e consistentes (clientes, apólices, sinistros, cláusulas).
3. Ter um plano B se a internet falhar no dia: prints de tela ou um vídeo curto gravado do fluxo funcionando, para não depender 100% de live demo em caso de problema de conectividade.
4. Decidir com antecedência em que momento exato da apresentação o painel de debug será aberto — isso deve parecer intencional, não improvisado.
