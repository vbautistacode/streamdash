# app/auth/login.py
import streamlit as st
from app.auth.auth_utils import get_connection, get_user_by_username, verify_password, is_admin

def show_login():
    # Inicializa estado
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["role"] = None
        st.session_state["user_name"] = None
        st.session_state["remember"] = False

    # Se já autenticado, mostra logout na sidebar e sai da função
    if st.session_state.get("authenticated", False):
        role = st.session_state.get("role") or ""
        user_name = st.session_state.get("user_name") or ""
        st.sidebar.success(f"Perfil: {role.capitalize()}" if role else "Perfil")
        if user_name:
            st.sidebar.write(f"Usuário: {user_name}")
        if st.sidebar.button("Logout"):
            st.session_state["authenticated"] = False
            st.session_state["role"] = None
            st.session_state["user_name"] = None
            st.session_state["remember"] = False
            st.experimental_rerun()
        return

    with st.form(key="login_form", clear_on_submit=False):
        cols = st.columns([1, 0.4])
        with cols[0]:
            username = st.text_input("Usuário", placeholder="seu.usuario", key="login_user")
            password = st.text_input("Senha", type="password", placeholder="••••••", key="login_pass")
            remember = st.checkbox("Lembrar", value=False, key="login_remember")
            # botão em coluna para alinhamento opcional
        cols = st.columns([1, 0.4])
        with cols[1]:
            submit = st.form_submit_button("Entrar")

        if submit:
            username_norm = username.strip() if isinstance(username, str) else username
            conn = None
            try:
                conn = get_connection()
                user = get_user_by_username(conn, username_norm)
            finally:
                if conn:
                    conn.close()

            if user and verify_password(password, user.get("password_hash")):
                st.session_state["authenticated"] = True
                st.session_state["role"] = user.get("role")
                st.session_state["user_name"] = user.get("name") or username_norm
                st.session_state["remember"] = bool(remember)
                st.success(f"Bem‑vindo {st.session_state['user_name']}!")
                st.experimental_rerun()
            else:
                st.error("Usuário ou senha incorretos")

    # Se ainda não autenticado, interrompe o app aqui
    if not st.session_state.get("authenticated", False):
        st.stop()
