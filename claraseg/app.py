import streamlit as st

st.set_page_config(
    page_title="ClaraSeg — Agente de Atendimento",
    page_icon="🛡️",
    layout="wide",
)

from ui.sidebar import render_sidebar
from ui.chat import render_chat
from ui.debug_panel import render_debug_panel

# Inicializa estado
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_debug_info" not in st.session_state:
    st.session_state.last_debug_info = None

try:
    customer_id, thread_id = render_sidebar()
except Exception as e:
    st.error(f"Erro ao conectar ao MongoDB: {e}")
    st.stop()

st.title("Clara — Agente ClaraSeg")
st.caption(f"Atendendo: **{st.session_state.get('selected_customer_name', '')}** · sessão `{thread_id[:20]}...`")

render_debug_panel()
st.divider()
render_chat(customer_id, thread_id)
