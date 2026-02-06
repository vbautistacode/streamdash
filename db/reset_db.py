import os
from db.models import get_connection, create_tables
from db.seed_db import seed_db

def reset_db():
    # Apaga o banco antigo
    if os.path.exists("streamdash.db"):
        os.remove("streamdash.db")
        print("🗑️ Banco antigo removido.")

    # Cria novo banco e tabelas
    conn = get_connection()
    create_tables(conn)
    conn.close()
    print("📦 Banco recriado com novo schema.")

    # Popula com dados fictícios
    seed_db()
    print("🌱 Banco populado com dados de exemplo (ClienteA aberta, ClienteB fechada).")

if __name__ == "__main__":
    reset_db()