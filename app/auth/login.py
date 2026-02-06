# app/auth/login.py
import streamlit as st
from app.auth.auth_utils import get_connection, get_user_by_username, verify_password, is_admin

def show_login():
    # Inicializa estado
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["role"] = None

    # Se já autenticado, mostra logout e sai da função
    if st.session_state["authenticated"]:
        st.sidebar.success(f"Perfil: {st.session_state['role'].capitalize()}")
        if st.sidebar.button("Logout"):
            st.session_state["authenticated"] = False
            st.session_state["role"] = None
            st.experimental_rerun()
        return

    # Renderiza somente o login
    st.title("🔐 Login")

    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        conn = get_connection()
        user = get_user_by_username(conn, username)
        conn.close()

        if user and verify_password(password, user["password_hash"]):
            st.session_state["authenticated"] = True
            st.session_state["role"] = user["role"]
            st.success(f"Bem-vindo {user['name']}!")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos")

    # Se ainda não autenticado, interrompe o app aqui
    st.stop()