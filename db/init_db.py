from db.connection import get_connection
from db.models import create_tables

def init_db():
    conn = get_connection()
    create_tables(conn)
    conn.close()
    print("✅ Banco inicializado com sucesso!")

if __name__ == "__main__":
    init_db()
