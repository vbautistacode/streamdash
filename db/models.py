# db/models.py

import sqlite3
from typing import Optional

def get_connection(db_path: str = "streamdash.db") -> sqlite3.Connection:
    """
    Retorna conexão SQLite configurada.
    - detect_types ajuda no parse de timestamps quando usado com pandas/sqlalchemy.
    - row_factory facilita leitura por cursors/ pandas (se necessário).
    - ativa foreign_keys por segurança.
    """
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    # -----------------------------
    # Financeiros (Fluxo de Caixa)
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS indicadores_financeiros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        mes TEXT NOT NULL,
        entradas REAL DEFAULT 0.0,
        saidas REAL DEFAULT 0.0,
        saldo REAL DEFAULT 0.0,
        caixa REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        UNIQUE(tenant_id, mes)
    )
    """)

    # -----------------------------
    # DRE Financeira
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dre_financeiro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        mes TEXT NOT NULL,
        receita_bruta REAL DEFAULT 0.0,
        deducoes REAL DEFAULT 0.0,
        custo_produto_vendido REAL DEFAULT 0.0,
        custo_servico_prestado REAL DEFAULT 0.0,
        despesas_vendas REAL DEFAULT 0.0,
        despesas_administrativas REAL DEFAULT 0.0,
        outras_despesas REAL DEFAULT 0.0,
        receitas_financeiras REAL DEFAULT 0.0,
        despesas_financeiras REAL DEFAULT 0.0,
        imposto_renda REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        UNIQUE(tenant_id, mes)
    )
    """)

    # -----------------------------
    # Vendas
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS indicadores_vendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        mes TEXT NOT NULL,
        volume_vendas REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        UNIQUE(tenant_id, mes)
    )
    """)

    # -----------------------------
    # Operacionais
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS indicadores_operacionais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        mes TEXT NOT NULL,
        vendas REAL DEFAULT 0.0,
        vendedores REAL DEFAULT 0.0,
        quantidade REAL DEFAULT 0.0,
        producao REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        UNIQUE(tenant_id, mes)
    )
    """)

    # -----------------------------
    # Marketing
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS indicadores_marketing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        mes TEXT NOT NULL,
        receita REAL DEFAULT 0.0,
        investimento REAL DEFAULT 0.0,
        leads_gerados REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        UNIQUE(tenant_id, mes)
    )
    """)

    # -----------------------------
    # Clientes
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS indicadores_clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        mes TEXT NOT NULL,
        clientes_ativos REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        UNIQUE(tenant_id, mes)
    )
    """)

    # -----------------------------
    # Contábeis
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dados_contabeis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        mes TEXT NOT NULL,
        patrimonio_liquido REAL DEFAULT 0.0,
        ativos REAL DEFAULT 0.0,
        ativo_circulante REAL DEFAULT 0.0,
        disponibilidade REAL DEFAULT 0.0,
        divida_bruta REAL DEFAULT 0.0,
        divida_liquida REAL DEFAULT 0.0,
        numero_papeis REAL DEFAULT 0.0,
        free_float REAL DEFAULT 0.0,
        segmento_listagem TEXT,
        tipo_empresa TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        UNIQUE(tenant_id, mes)
    )
    """)

    # -----------------------------
    # Índices úteis
    # -----------------------------
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_financeiros_tenant_mes ON indicadores_financeiros (tenant_id, mes);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dre_tenant_mes ON dre_financeiro (tenant_id, mes);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendas_tenant_mes ON indicadores_vendas (tenant_id, mes);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_oper_tenant_mes ON indicadores_operacionais (tenant_id, mes);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_marketing_tenant_mes ON indicadores_marketing (tenant_id, mes);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clientes_tenant_mes ON indicadores_clientes (tenant_id, mes);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contabeis_tenant_mes ON dados_contabeis (tenant_id, mes);")

    conn.commit()
    cursor.close()

if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    conn.close()

# db/models.py  (adicione abaixo de create_tables)

import pandas as pd
from typing import Dict, Any
from app.dashboards.utils_calc import calc_estrategicos_from_dre

def fetch_tables_for_tenant(tenant_id: str, periodo: str = "2025-01", acumulado: bool = False, db_path: str = "streamdash.db") -> Dict[str, pd.DataFrame]:
    """
    Retorna DataFrames filtrados por tenant e período.
    - periodo: 'YYYY-MM'
    - acumulado: se True retorna todos os meses <= periodo (lexicográfico ok para YYYY-MM)
    Retorna dict com chaves: finance, dre, vendas, operacional, marketing, clientes, contabeis, derived_metrics
    """
    conn = get_connection(db_path)
    dfs: Dict[str, pd.DataFrame] = {}

    if acumulado:
        period_where = f"mes <= '{periodo}'"
    else:
        period_where = f"mes = '{periodo}'"

    tables = {
        "finance": "indicadores_financeiros",
        "dre": "dre_financeiro",
        "vendas": "indicadores_vendas",
        "operacional": "indicadores_operacionais",
        "marketing": "indicadores_marketing",
        "clientes": "indicadores_clientes",
        "contabeis": "dados_contabeis"
    }

    for key, table in tables.items():
        q = f"SELECT * FROM {table} WHERE tenant_id = ? AND {period_where} ORDER BY mes"
        try:
            dfs[key] = pd.read_sql_query(q, conn, params=(tenant_id,))
        except Exception:
            dfs[key] = pd.DataFrame()

    conn.close()

    # calcula derived_metrics a partir da DRE e contábeis
    try:
        derived = calc_estrategicos_from_dre(dfs.get("dre"), dfs.get("contabeis"))
    except Exception:
        derived = {}
    # anexa o dicionário (não é DataFrame)
    dfs["derived_metrics"] = derived
    return dfs