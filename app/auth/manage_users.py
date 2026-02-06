# app/auth/manage_users.py
import streamlit as st
from app.auth.auth_utils import get_connection, create_user, get_user_by_username, hash_password

def show_manage_users():
    # Apenas admins podem acessar
    if st.session_state.get("role") != "admin":
        st.error("Acesso restrito: apenas administradores podem gerenciar usuários.")
        return

    st.subheader("👥 Gestão de Usuários")

    conn = get_connection()
    cur = conn.cursor()

    # Listar usuários existentes
    st.markdown("### Usuários existentes")
    try:
        cur.execute("SELECT id, name, username, role, created_at FROM users")
        rows = cur.fetchall()
        if rows:
            for r in rows:
                st.write(f"**{r[1]}** ({r[2]}) — Role: {r[3]} — Criado em {r[4]}")
        else:
            st.info("Nenhum usuário cadastrado.")
    except Exception as e:
        st.error(f"Erro ao listar usuários: {e}")

    st.divider()

    # Formulário para criar novo usuário
    st.markdown("### Criar novo usuário")
    with st.form("create_user_form"):
        name = st.text_input("Nome")
        username = st.text_input("Username")
        password = st.text_input("Senha", type="password")
        role = st.selectbox("Role", ["viewer", "admin"])
        submitted = st.form_submit_button("Criar usuário")

        if submitted:
            try:
                create_user(conn, name, username, password, role)
                st.success(f"Usuário {username} criado com sucesso!")
            except Exception as e:
                st.error(f"Erro ao criar usuário: {e}")

    st.divider()

    # Formulário para remover usuário
    st.markdown("### Remover usuário")
    username_del = st.text_input("Username para remover")
    if st.button("Remover"):
        try:
            cur.execute("DELETE FROM users WHERE username = %s" if conn.__class__.__name__ == "psycopg2.extensions.connection" else "DELETE FROM users WHERE username = ?", (username_del,))
            conn.commit()
            st.success(f"Usuário {username_del} removido com sucesso!")
        except Exception as e:
            st.error(f"Erro ao remover usuário: {e}")

    cur.close()
    conn.close()