# check_db.py
import sqlite3
import pandas as pd
from pathlib import Path

DB = Path("streamdash.db")
print("DB exists:", DB.exists(), "path:", DB.resolve())

if not DB.exists():
    raise SystemExit("Arquivo DB não encontrado no caminho acima.")

conn = sqlite3.connect(str(DB))
tables = []
try:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    print("\nTables:", tables)
except Exception as e:
    print("Erro listando tabelas:", e)

# Função utilitária para mostrar amostra e nulos
def sample_and_nulls(table, limit=5):
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT {limit}", conn)
        print(f"\n== {table} (rows sample {len(df)})")
        print(df.head(limit).to_string(index=False))
        # total rows
        total = pd.read_sql_query(f"SELECT COUNT(*) as cnt FROM {table}", conn).iloc[0,0]
        print("total rows:", int(total))
        # null counts
        full = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 1000", conn)  # safe sample for nulls
        print("null counts (sample up to 1000 rows):")
        print(full.isna().sum().to_string())
    except Exception as e:
        print(f"Erro ao ler {table}: {e}")

# ver tabelas esperadas e amostras
expected = [
    "dre_financeiro", "dados_contabeis", "indicadores_vendas",
    "indicadores_financeiros", "indicadores_marketing",
    "indicadores_operacionais", "indicadores_clientes"
]

for t in expected:
    if t in tables:
        sample_and_nulls(t)
    else:
        print(f"\nTabela esperada ausente: {t}")

conn.close()