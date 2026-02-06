# app/auth/init_users.py
from app.auth.auth_utils import get_connection, create_user

def init_admin_user():
    conn = get_connection()
    try:
        create_user(conn, "Administrador", "admin", "admin123", "admin")
        print("Usuário admin criado com sucesso.")
    except Exception as e:
        print("Erro ou usuário já existe:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    init_admin_user()