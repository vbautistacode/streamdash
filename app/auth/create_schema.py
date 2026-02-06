# app/auth/create_schema.py
import sqlite3

def create_users_table():
    conn = sqlite3.connect("streamdash.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT CHECK (role IN ('admin','viewer')) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print("Tabela 'users' criada com sucesso.")

if __name__ == "__main__":
    create_users_table()