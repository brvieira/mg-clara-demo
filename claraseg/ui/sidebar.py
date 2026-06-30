import uuid
import streamlit as st

from src.db import get_db
from src.config import CUSTOMER_PROFILE_COLLECTION


def _load_customers() -> list[dict]:
    return list(get_db()[CUSTOMER_PROFILE_COLLECTION].find({}, {"_id": 0, "customer_id": 1, "name": 1}))


def render_sidebar() -> tuple[str, str]:
    """Renderiza a sidebar e retorna (customer_id, thread_id) ativos."""
    with st.sidebar:
        st.title("ClaraSeg")
        st.caption("Agente de atendimento — demo")
        st.divider()

        # Carrega clientes apenas uma vez
        if "customers" not in st.session_state:
            st.session_state.customers = _load_customers()

        customers = st.session_state.customers
        customer_labels = {c["name"]: c["customer_id"] for c in customers}
        names = list(customer_labels.keys())

        selected_name = st.selectbox("Cliente", names, key="selected_customer_name")
        selected_customer_id = customer_labels[selected_name]

        # Detecta troca de cliente → inicia nova sessão
        if st.session_state.get("customer_id") != selected_customer_id:
            st.session_state.customer_id = selected_customer_id
            st.session_state.thread_id = f"{selected_customer_id}_{uuid.uuid4().hex[:8]}"
            st.session_state.chat_history = []
            st.session_state.last_debug_info = None

        st.divider()
        st.markdown("**Sessão atual**")
        thread_short = st.session_state.thread_id[:24] + "..."
        st.code(thread_short, language=None)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Nova conversa", use_container_width=True):
                st.session_state.thread_id = f"{selected_customer_id}_{uuid.uuid4().hex[:8]}"
                st.session_state.chat_history = []
                st.session_state.last_debug_info = None
                st.rerun()

        with col2:
            if st.button("Resetar demo", use_container_width=True):
                _reset_demo()
                st.rerun()

    return st.session_state.customer_id, st.session_state.thread_id


def _reset_demo() -> None:
    """Re-executa o seed para restaurar dados ao estado inicial."""
    from src.seed import run as seed_run
    with st.spinner("Resetando dados..."):
        seed_run()
    st.session_state.chat_history = []
    st.session_state.last_debug_info = None
    st.success("Dados resetados.")
