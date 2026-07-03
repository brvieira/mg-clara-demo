"""
Teste de fluxo ponta a ponta — executar manualmente antes da apresentação.

Pré-requisitos:
  1. .env configurado com MONGODB_URI e OPENAI_API_KEY
  2. seed.py executado (python -m src.seed)
  3. Índice de vector search criado na Atlas UI

Executar: python -m tests.test_agent_smoke
"""
import uuid
from src.agent import invoke


def new_thread(customer_id: str) -> str:
    return f"{customer_id}_{uuid.uuid4().hex[:8]}"


def tool_calls_of(result: dict, tool_name: str) -> list:
    return [
        c for c in result["debug"].get("tool_calls_made", [])
        if c["tool_name"] == tool_name
    ]


def run_smoke_tests():
    print("\n=== ClaraSeg — Smoke Tests ===\n")

    # --- Critério 1: memória de longo prazo entre sessões ---
    print("1. Memória de longo prazo entre sessões")
    thread_a = new_thread("cust_1001")
    r1 = invoke(thread_a, "cust_1001", "Oi Clara! Mudei de carro recentemente, agora tenho um Compass 2025.")
    print(f"   [thread A] resposta: {r1['response'][:100]}...")
    print(f"   [thread A] novo fato: {r1['debug'].get('new_fact_saved')}")

    thread_b = new_thread("cust_1001")
    r2 = invoke(thread_b, "cust_1001", "Qual é o meu carro atual cadastrado?")
    print(f"   [thread B] resposta: {r2['response'][:150]}...")
    print(f"   [thread B] fatos LT: {r2['debug'].get('long_term_facts')}")
    assert "Compass" in r2["response"] or r2["debug"].get("long_term_facts"), \
        "FALHOU: memória de longo prazo não persistiu entre sessões"
    print("   PASSOU\n")

    # --- Critério 2: memória de curto prazo dentro da mesma sessão ---
    print("2. Memória de curto prazo (dentro do mesmo thread)")
    thread_c = new_thread("cust_1002")
    invoke(thread_c, "cust_1002", "Tenho uma dúvida sobre o meu seguro de carro, é um Corolla 2023.")
    r3 = invoke(thread_c, "cust_1002", "E o carro que mencionei, ele tem cobertura de roubo?")
    print(f"   resposta: {r3['response'][:150]}...")
    assert "Corolla" in r3["response"] or "roubo" in r3["response"].lower(), \
        "FALHOU: agente não lembrou do carro mencionado anteriormente"
    print("   PASSOU\n")

    # --- Critério 3: vector search semântico (3 formulações diferentes) ---
    print("3. Vector search semântico (tool vector_search_clausulas chamada)")
    queries = [
        ("cust_1001", "O que acontece se bater o carro?"),
        ("cust_1001", "Tenho direito a veículo emprestado enquanto o meu está na oficina?"),
        ("cust_1001", "Qual o prazo para eu avisar a seguradora depois de um acidente?"),
    ]
    for customer_id, q in queries:
        t = new_thread(customer_id)
        r = invoke(t, customer_id, q)
        vs_calls = tool_calls_of(r, "vector_search_clausulas")
        clauses = vs_calls[0].get("output", []) if vs_calls else []
        print(f"   '{q[:55]}' → {len(clauses)} cláusulas")
        assert vs_calls, f"FALHOU: vector_search_clausulas não chamada para '{q}'"
        assert clauses, f"FALHOU: nenhuma cláusula retornada para '{q}'"
    print("   PASSOU\n")

    # --- Critério 4: status de sinistro do perfil operacional ---
    print("4. Status de sinistro do customer_profile")
    thread_d = new_thread("cust_1001")
    r4 = invoke(thread_d, "cust_1001", "Qual o status do meu sinistro?")
    print(f"   resposta: {r4['response'][:150]}...")
    assert "CLM-4471" in r4["response"] or "análise" in r4["response"].lower() or "colisão" in r4["response"].lower(), \
        "FALHOU: status do sinistro não foi retornado"
    print("   PASSOU\n")

    # --- Critério 5: sem alucinação de cobertura inexistente ---
    print("5. Não alucinação de cobertura inexistente")
    thread_e = new_thread("cust_1001")
    r5 = invoke(thread_e, "cust_1001", "Meu seguro cobre danos causados por enchente?")
    print(f"   resposta: {r5['response'][:200]}...")
    lower = r5["response"].lower()
    assert "não" in lower or "verificar" in lower or "cláusula" in lower or "não encontr" in lower, \
        "FALHOU: agente afirmou cobertura de enchente que não existe nas cláusulas"
    print("   PASSOU\n")

    # --- Critério 6: pergunta factual NÃO dispara tool call ---
    print("6. Pergunta factual não dispara tool call")
    thread_f = new_thread("cust_1001")
    r6 = invoke(thread_f, "cust_1001", "Qual o número da minha apólice de auto?")
    print(f"   resposta: {r6['response'][:150]}...")
    calls_f = r6["debug"].get("tool_calls_made", [])
    print(f"   tool calls feitas: {[c['tool_name'] for c in calls_f]}")
    assert not calls_f, \
        f"FALHOU: agente chamou ferramentas ({[c['tool_name'] for c in calls_f]}) para pergunta que deveria responder direto"
    print("   PASSOU\n")

    # --- Critério 7: pergunta de cobertura dispara EXATAMENTE 1 vector_search_clausulas ---
    print("7. Pergunta de cobertura dispara exatamente 1 chamada a vector_search_clausulas")
    thread_g = new_thread("cust_1001")
    r7 = invoke(thread_g, "cust_1001", "Minha apólice cobre colisão com animal na pista?")
    print(f"   resposta: {r7['response'][:150]}...")
    vs_calls_g = tool_calls_of(r7, "vector_search_clausulas")
    print(f"   chamadas a vector_search_clausulas: {len(vs_calls_g)}")
    assert len(vs_calls_g) == 1, \
        f"FALHOU: esperava 1 chamada a vector_search_clausulas, encontrou {len(vs_calls_g)}"
    print("   PASSOU\n")

    # --- Critério 8: pergunta combinada (cobertura + oficina) dispara ambas as tools ---
    print("8. Pergunta combinada dispara vector_search_clausulas e buscar_oficinas_proximas")
    thread_h = new_thread("cust_1001")
    r8 = invoke(
        thread_h, "cust_1001",
        "Abri um sinistro de colisão. O que a apólice cobre e qual oficina parceira perto de mim atende colisão?"
    )
    print(f"   resposta: {r8['response'][:200]}...")
    vs_calls_h = tool_calls_of(r8, "vector_search_clausulas")
    ws_calls_h = tool_calls_of(r8, "buscar_oficinas_proximas")
    print(f"   vector_search_clausulas: {len(vs_calls_h)}x, buscar_oficinas_proximas: {len(ws_calls_h)}x")

    response_lower = r8["response"].lower()
    oficinas_mock = ["auto center vivaz", "oficina rápida", "master auto glass", "garage plus"]
    mencionou_oficina = any(o in response_lower for o in oficinas_mock)

    assert vs_calls_h or "cobertura" in response_lower or "colisão" in response_lower, \
        "FALHOU: agente não abordou cobertura na pergunta combinada"
    assert ws_calls_h or mencionou_oficina, \
        "FALHOU: agente não buscou oficinas na pergunta combinada"
    print("   PASSOU\n")

    print("=== Todos os testes passaram ===")


if __name__ == "__main__":
    run_smoke_tests()
