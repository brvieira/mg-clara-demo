import json
import streamlit as st


def _parse_mcp_item(item: dict) -> dict:
    """Converte content block MCP {type, text, id} para dict plano se necessário."""
    if isinstance(item, dict) and item.get("type") == "text":
        try:
            return json.loads(item["text"])
        except (json.JSONDecodeError, KeyError):
            pass
    return item


def render_debug_panel() -> None:
    debug = st.session_state.get("last_debug_info")
    if not debug:
        return

    with st.expander("Painel de transparência — o que o agente recuperou", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Memória de longo prazo")
            facts = debug.get("long_term_facts", [])
            if facts:
                for f in facts:
                    st.markdown(f"- {f.get('fact', '')}")
                    st.caption(f"Registrado em: {f.get('recorded_at', '')}")
            else:
                st.caption("Nenhum fato persistido para este cliente.")

            st.markdown("#### Novo fato gravado nesta interação")
            new_fact = debug.get("new_fact_saved")
            if new_fact:
                st.success(new_fact.get("fact", ""))
            else:
                st.caption("Nenhum fato novo identificado.")

        with col2:
            st.markdown("#### Tool calls deste turno")
            calls = debug.get("tool_calls_made", [])
            if not calls:
                st.caption("Nenhuma tool chamada — resposta direta do LLM.")
            else:
                for call in calls:
                    tool_name = call.get("tool_name", "?")
                    tool_input = call.get("input", {})
                    tool_output = call.get("output")

                    st.markdown(f"**`{tool_name}`**")
                    st.caption(f"Input: `{json.dumps(tool_input, ensure_ascii=False)}`")

                    if tool_output is not None:
                        if tool_name == "vector_search_clausulas" and isinstance(tool_output, list):
                            for clause in tool_output:
                                score = clause.get("score", "?")
                                section = clause.get("section") or clause.get("source_file", "?")
                                st.markdown(f"  - **{section}** `score: {score}`")
                                with st.expander(f"Ver texto — {clause.get('source_file', '')}", expanded=False):
                                    st.write(clause.get("text", ""))
                        elif tool_name == "buscar_oficinas_proximas" and isinstance(tool_output, list):
                            for item in tool_output:
                                oficina = _parse_mcp_item(item)
                                st.markdown(
                                    f"  - **{oficina.get('nome', '?')}** — "
                                    f"{oficina.get('distancia_km', '?')} km "
                                    f"· `{oficina.get('oficina_id', '?')}`"
                                )
                        elif tool_name == "consultar_agenda_pericia" and isinstance(tool_output, list):
                            for item in tool_output:
                                slot = _parse_mcp_item(item)
                                st.markdown(
                                    f"  - {slot.get('data', '?')} às {slot.get('horario', '?')}"
                                )
                        else:
                            st.json(tool_output)

                    st.divider()

        with st.expander("Raw debug (diagnóstico)", expanded=False):
            st.json(debug)
