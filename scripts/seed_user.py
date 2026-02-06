#!/usr/bin/env python3
"""
scripts/seed_user.py

Seed or update a user in a local SQLite database for Streamdash using Argon2.
Usage:
  python scripts/seed_user.py --db streamdash.db --username test_user --password 'Test@1234' --name "Usuário de Teste" --role admin
"""

import argparse
import sqlite3
from pathlib import Path
import sys
from passlib.hash import argon2

DEFAULT_DB = "streamdash.db"

USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT CHECK (role IN ('admin','viewer')) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

UPSERT_SQL = """
INSERT INTO users (name, username, password_hash, role)
VALUES (?, ?, ?, ?)
ON CONFLICT(username) DO UPDATE SET
  password_hash = excluded.password_hash,
  name = excluded.name,
  role = excluded.role;
"""

def parse_args():
    p = argparse.ArgumentParser(description="Seed or update a user in SQLite DB (Argon2)")
    p.add_argument("--db", default=DEFAULT_DB, help="Path to SQLite DB file")
    p.add_argument("--username", required=True, help="Username to create or update")
    p.add_argument("--password", required=True, help="Plaintext password for the user")
    p.add_argument("--name", default=None, help="Full name for the user")
    p.add_argument("--role", choices=["admin", "viewer"], default="viewer", help="User role")
    return p.parse_args()

def ensure_db_and_table(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.executescript(USERS_TABLE_SQL)
    conn.commit()
    return conn

def hash_password(plain: str) -> str:
    # normalize whitespace and ensure string type
    pw = "" if plain is None else str(plain).strip()
    return argon2.hash(pw)

def seed_user(conn, name: str, username: str, password_hash: str, role: str):
    cur = conn.cursor()
    cur.execute(UPSERT_SQL, (name, username, password_hash, role))
    conn.commit()

def main():
    args = parse_args()
    db_path = Path(args.db)

    # Ensure parent dir exists for DB if needed
    if not db_path.parent.exists():
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Erro ao criar diretório para DB: {e}", file=sys.stderr)
            sys.exit(1)

    conn = ensure_db_and_table(db_path)

    name = args.name if args.name else args.username
    try:
        password_hash = hash_password(args.password)
    except Exception as e:
        print(f"Erro ao gerar hash da senha: {e}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    try:
        seed_user(conn, name, args.username, password_hash, args.role)
    except Exception as e:
        print(f"Erro ao inserir/atualizar usuário: {e}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    conn.close()
    print(f"Usuário seedado/atualizado: username='{args.username}', role='{args.role}', db='{db_path}'")
    print("Senha em texto claro não é armazenada. Use a senha fornecida para login no app.")

if __name__ == "__main__":
    main()