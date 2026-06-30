import streamlit as st
from src import agent


def render_chat(customer_id: str, thread_id: str) -> None:
    # Exibe histórico
    for msg in st.session_state.get("chat_history", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    user_input = st.chat_input("Digite sua mensagem...")
    if not user_input:
        return

    # Exibe mensagem do usuário imediatamente
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Chama o agente
    with st.chat_message("assistant"):
        with st.spinner("Clara está pensando..."):
            try:
                result = agent.invoke(thread_id, customer_id, user_input)
                response = result["response"]
                st.session_state.last_debug_info = result["debug"]
            except Exception as e:
                response = f"Erro ao processar sua mensagem. Por favor, tente novamente."
                st.error(f"Detalhe técnico: {e}")
                st.session_state.last_debug_info = None

        st.markdown(response)
        st.session_state.chat_history.append({"role": "assistant", "content": response})

    st.rerun()
