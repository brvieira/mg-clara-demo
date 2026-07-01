# Clara — Contexto e Solução

## 1. Cenário de negócio

### 1.1 A empresa fictícia: Vivaz Seguros

Uma seguradora fictícia de médio porte — **Vivaz Seguros** — atuando nos ramos de **auto e residencial**, com aproximadamente 200 mil segurados ativos no Brasil.

### 1.2 O desafio de negócio

O time de atendimento ao cliente da Vivaz recebe um volume alto de contatos recorrentes sobre três temas: dúvidas de cobertura de apólice, status de sinistro em andamento, e atualização de dados cadastrais. Hoje, esse atendimento enfrenta três dores específicas:

1. **Falta de memória entre contatos.** Quando um cliente liga ou envia mensagem mais de uma vez sobre o mesmo assunto, o atendente não tem visibilidade fácil do que já foi discutido — o cliente precisa repetir contexto, o que aumenta o tempo de atendimento e gera frustração.

2. **Consulta manual e lenta às cláusulas contratuais.** Perguntas sobre cobertura específica exigem que o atendente busque manualmente no contrato — um processo lento, sujeito a erro humano, e que escala mal com o volume de chamados.

3. **Dados operacionais fragmentados.** Informações de apólice, sinistro e histórico de interação muitas vezes vivem em sistemas ou planilhas separadas, dificultando uma visão unificada do cliente no momento do atendimento.

## 2. Visão Geral da Solução

**ClaraSeg** é um agente conversacional capaz de responder, em linguagem natural, perguntas sobre cobertura de apólice, status de sinistro e localização de oficinas parceiras, mantendo:

- **Memória de curto prazo:** contexto da conversa atual, permitindo que o cliente faça perguntas de acompanhamento sem repetir informação já fornecida na mesma sessão.
- **Memória de longo prazo:** fatos relevantes sobre o cliente que persistem entre sessões diferentes (ex: uma mudança de veículo mencionada em um contato anterior é lembrada em um contato futuro).
- **Busca semântica nas cláusulas contratuais** permitindo que perguntas formuladas livremente pelo cliente — sem usar a terminologia exata do contrato — encontrem a cláusula correta.
- **Integração com sistemas externos** via MCP (Model Context Protocol), permitindo que o agente consulte a rede de oficinas parceiras e agende perícias sem acoplar essa lógica ao codebase principal.
  |
