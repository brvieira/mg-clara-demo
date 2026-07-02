# Roteiro de Demonstração — ClaraSeg

Três cenários independentes, cada um isolando **uma** capacidade arquitetural da solução. Cada cenário tem um cliente fictício dedicado (para não misturar sinais na hora de explicar) e pode ser apresentado sozinho ou em sequência.

| Cenário | Capacidade demonstrada | Cliente |
|---|---|---|
| 1 | Memória de curto prazo (checkpointer) + memória de longo prazo (store) | Marina Torres (`cust_1004`) |
| 2 | Dado persistente/operacional (`customer_profile` — apólices e sinistros) | Ana Paula Ferreira (`cust_1002`) |
| 3 | Integração via MCP com sistema externo (rede de oficinas parceiras) | Carlos Mendonça (`cust_1001`) |

**Antes de apresentar:** os dados de `cust_1004` e o sinistro `CLM-5528` de `cust_1002` foram adicionados ao seed para viabilizar os Cenários 1 e 2. Rode `python data/seed.py` (ou clique em **"Resetar demo"** na sidebar) antes de começar, para garantir que o banco está no estado esperado por este roteiro.

---

## Cenário 1 — Memória de curto e longo prazo

### Business problem

O time de atendimento da Vivaz Seguros recebe contatos recorrentes do mesmo cliente sobre o mesmo assunto — por telefone, WhatsApp, e-mail — muitas vezes com atendentes diferentes a cada vez. Hoje, se o cliente mencionou algo relevante numa ligação de terça (ex: "troquei de carro"), essa informação normalmente não chega ao atendente que fala com ele na sexta. O cliente é obrigado a repetir contexto do zero a cada contato, o que aumenta o tempo médio de atendimento (TMA) e gera a sensação de "a seguradora não me conhece" — mesmo quando o cliente já é segurado há anos.

### Como a solução resolve

O agente ClaraSeg mantém duas camadas de memória, fisicamente separadas, com propósitos diferentes:

- **Curto prazo (`MongoDBSaver`, coleção `short_term_memory`):** todo o histórico de mensagens da conversa atual, indexado por `thread_id`. Permite perguntas de acompanhamento sem repetir contexto — mas se perde quando a sessão termina.
- **Longo prazo (`MongoDBStore`, coleção `long_term_memory`):** fatos extraídos e classificados como duradouros (mudança de veículo, endereço, preferência de contato), indexados por `customer_id` — **independente de qual sessão está ativa**. Sobrevive ao fim da conversa e a trocas de canal/atendente.

O ponto que mais impacta na demo: ao abrir uma sessão **totalmente nova** (thread zerado, como se fosse um contato inédito), o agente ainda lembra do fato — porque ele nunca esteve no histórico de mensagens, e sim numa coleção separada, consultada a cada turno pelo nó `load_memory`.

### Roteiro

1. Na sidebar, selecione **"Marina Torres"**. Uma nova sessão é criada automaticamente (thread A).

2. Envie:
   > Oi, aqui é a Marina. Troquei de carro semana passada — vendi o Fiesta e comprei um Jeep Compass 2025. Só queria deixar registrado com vocês.

   Não é uma pergunta de cobertura, então nenhuma tool é acionada. Abra o painel de debug: mostre que um **novo fato foi gravado** (`vehicle_change` → "Compass 2025"). Esse é o momento em que o fato é escrito no `MongoDBStore` pelo nó `save_memory`.

3. Ainda na mesma sessão, envie (memória de **curto** prazo):
   > E a cobertura de roubo e furto continua valendo do mesmo jeito pro carro novo?

   O agente responde sem perguntar "qual carro?" — ele já tem isso no histórico da conversa atual (nenhuma consulta ao banco foi necessária para isso, é o `messages` do state). Ao mesmo tempo, aciona `vector_search_clausulas` para trazer a Cláusula 2.3 (Cobertura de Roubo e Furto) da apólice de auto. Mostre no painel de debug a cláusula recuperada com o score.

4. Clique em **"Nova conversa"** na sidebar. O `thread_id` muda (thread B) e o chat visualmente zera — deixe claro para a plateia que isso é intencional: **a memória de curto prazo foi descartada**.

5. Na nova sessão, envie:
   > Bom dia! Só confirmando: ficou registrado que troquei de carro mesmo? Qual carro consta aí pra mim agora?

   Mesmo em uma sessão que nunca viu essa conversa, o agente responde corretamente com o Jeep Compass 2025. Abra o painel de debug e mostre a seção de **fatos de longo prazo** já populada no início do turno — antes mesmo do LLM responder, `load_memory` já buscou o fato no `MongoDBStore` usando `customer_id`, não `thread_id`.

**O contraste a explicitar:** passo 4 prova que a memória de curto prazo foi apagada; passo 5 prova que a memória de longo prazo sobreviveu. As duas camadas são independentes — e é exatamente essa independência que resolve a dor de negócio.

---

## Cenário 2 — Dado persistente e operacional

### Business problem

Apólices, sinistros e histórico de interação da Vivaz hoje vivem espalhados: o sistema de apólices é um, o de sinistros é outro, e o atendente frequentemente precisa alternar entre telas (ou sistemas diferentes) para montar uma visão completa do cliente durante a ligação. Isso tem dois efeitos ruins: o atendimento fica mais lento (o atendente está "procurando" enquanto o cliente espera), e o cliente é obrigado a fornecer de novo dados que a seguradora já tem — número de sinistro, placa do carro, data de renovação — o que soa burocrático e impessoal.

### Como a solução resolve

A coleção `customer_profile` centraliza apólices e sinistros do cliente num único documento MongoDB, carregado pelo nó `load_memory` **a cada turno**, antes de qualquer raciocínio do LLM. Diferente da memória de longo prazo (fatos aprendidos em conversa), esse é dado operacional gerido diretamente pela aplicação — a fonte de verdade sobre o que o cliente contratou e o que já foi acionado.

Isso permite dois comportamentos que a demo evidencia lado a lado:
- Quando o cliente relata algo que **corresponde a um sinistro já existente**, o agente reconhece isso proativamente e cita número e status — sem que o cliente precise informar.
- Quando o cliente pergunta um **dado cadastral direto** (data de renovação, número de apólice), o agente responde imediatamente do perfil, sem acionar nenhuma ferramenta — mostrando que nem toda resposta depende de busca; dado estruturado já disponível é usado diretamente.

### Roteiro

1. Na sidebar, selecione **"Ana Paula Ferreira"** — ela tem duas apólices ativas (auto e residencial) e um sinistro residencial em análise.

2. Envie:
   > Oi, aqui é a Ana Paula. Semana passada estourou um cano da caixa d'água aqui em casa e vazou água pro chão da sala, molhou o piso e o rodapé todo.

   Observe a estrutura da resposta: (1) acolhimento citando o nome dela; (2) o agente encontra no perfil o sinistro `CLM-5528` (tipo `vazamento`, status `em_analise`) e cita número e status **sem que ela tenha mencionado o número do sinistro**; (3) aciona `vector_search_clausulas` e traz a Cláusula 3.4 (Danos Causados por Água), explicando a condição de cobertura (vazamento súbito de tubulação interna, e não infiltração gradual).

   **Detalhe técnico para destacar:** como Ana Paula tem *dois* tipos de apólice (auto + residencial), o filtro automático por categoria do vector search **não** é aplicado (ele só é usado quando o cliente tem exatamente um tipo de apólice) — mesmo assim a cláusula certa é recuperada pela relevância semântica. É um bom contraste com o Cenário 3, onde Carlos (só auto) teria o filtro aplicado automaticamente.

3. Na mesma sessão, envie:
   > Entendi, obrigada! Ah, e minha apólice de auto, quando renova mesmo? Sempre esqueço a data.

   O agente responde diretamente com `2026-09-15`, vindo do campo `renewal_date` do perfil. Abra o painel de debug e mostre que **nenhuma tool foi chamada** nesse turno — o dado já estava carregado em `customer_profile` desde o início do turno pelo `load_memory`, então não há necessidade de busca semântica nem de qualquer chamada externa.

**O contraste a explicitar:** a mesma fonte de dado (`customer_profile`) alimenta tanto o reconhecimento proativo do sinistro (passo 2) quanto a resposta direta e sem tool call (passo 3) — é a unificação de apólice + sinistro num único lugar que elimina a fragmentação descrita no problema de negócio.

---

## Cenário 3 — Integração via MCP com sistema externo

### Business problem

A rede de oficinas e peritos parceiros da Vivaz não é operada pela seguradora — é um sistema de terceiros, fora da governança do time de TI da Vivaz. Hoje, agendar uma perícia nessa rede envolve ligação telefônica ou troca de e-mails entre o atendente e o parceiro, o que é lento e sujeito a erro humano — incluindo o risco real de duplicar agendamentos para o mesmo cliente em oficinas diferentes, gerando confusão logística e custo desnecessário para a seguradora.

### Como a solução resolve

O agente se conecta à rede de oficinas parceiras através do **Model Context Protocol (MCP)** — um protocolo aberto que expõe um contrato padronizado de ferramentas (nome, parâmetros, descrição) sem acoplar o código do agente à implementação do parceiro. Na demo, isso é simulado por um servidor MCP standalone (`workshop-mcp/`), rodando como processo isolado, que expõe cinco ferramentas: busca de oficinas por proximidade e serviço, consulta de agenda, confirmação de agendamento, listagem e alteração/cancelamento.

O ponto mais importante para a plateia: a regra de negócio "um cliente só pode ter um agendamento em aberto por vez" **vive no sistema do parceiro, não no agente**. Quando violada, o parceiro recusa e devolve os dados do agendamento conflitante — e é papel do agente (não de código customizado da Vivaz) interpretar essa recusa e conduzir o cliente à resolução. Isso é o desacoplamento real: o agente nunca conhece a lógica interna do parceiro, apenas reage ao contrato da ferramenta.

### Roteiro

1. Na sidebar, selecione **"Carlos Mendonça"** — ele tem um sinistro de colisão em análise (`CLM-4471`).

2. Envie:
   > Bom dia, sou eu de novo sobre a colisão no estacionamento. Preciso levar o carro pra vistoria numa oficina parceira de vocês, tem alguma perto de mim?

   O agente reconhece o sinistro existente, e então aciona a ferramenta MCP `buscar_oficinas_proximas` (CEP do perfil + `tipo_servico="colisao"`). Abra o painel de debug: mostre a seção de tool calls com o resultado bruto vindo do **subprocesso MCP** — 3 oficinas ordenadas por distância.

3. Envie:
   > Pode ver os horários disponíveis na Auto Center Vivaz Zona Sul? Prefiro o quanto antes.

   Aciona `consultar_agenda_pericia` (`urgencia="urgente"`) — retorna os 3 próximos horários, começando no dia seguinte.

4. Envie:
   > Perfeito, fecha aí no primeiro horário.

   Aciona `agendar_pericia` com os dados exatos retornados no passo anterior — confirmação com um `agendamento_id` novo.

5. Envie:
   > Só confirmando, quais agendamentos eu tenho marcados?

   Aciona `listar_agendamentos_cliente` — mostra o agendamento recém-criado, com status `confirmado`. Esse é o momento de mostrar que o agente está consultando o estado real do sistema parceiro, não repetindo algo que "lembrou" de antes.

6. Agora o momento-chave — force o conflito. Envie:
   > Pensei melhor, prefiro tentar na Garage Plus Mecânica Especializada em vez dessa. Pode agendar lá também?

   O agente tenta `agendar_pericia` na nova oficina; o servidor MCP **recusa** (`cliente_ja_possui_agendamento_aberto`) e devolve os dados do agendamento existente. O agente explica a situação ao cliente e pergunta se ele quer cancelar ou remarcar o agendamento atual antes de tentar de novo — **sem que essa regra tenha sido escrita no prompt do agente**; ela veio da resposta da ferramenta.

7. Envie:
   > Ah verdade, esqueci que já tinha marcado. Pode só mudar o horário desse pra mais tarde, tipo 14h30, no mesmo dia?

   Aciona `alterar_agendamento` com o novo horário — confirmação final.

**O contraste a explicitar:** do ponto de vista do grafo, `vector_search_clausulas` (função Python local) e as ferramentas de oficina (processo externo via MCP) passam pelo mesmo `tools_node` — o LLM decide a sequência de chamadas dinamicamente, sem saber (nem precisar saber) que uma é local e a outra é um sistema de terceiro rodando em outro processo.

---

## Notas de apresentação

- Os três cenários são independentes — podem ser demonstrados em qualquer ordem, ou isoladamente se o tempo for curto.
- Tempo estimado: ~4-5 min por cenário incluindo explicação, ~15 min para os três.
- Use o botão **"Resetar demo"** entre apresentações para garantir que os agendamentos criados no Cenário 3 e os fatos gravados no Cenário 1 não se acumulem de uma sessão de demo para a próxima.
- O painel de debug (`st.expander`) deve ficar aberto durante toda a demonstração — é ele que transforma cada cenário de uma caixa-preta em uma explicação explícita da arquitetura.
