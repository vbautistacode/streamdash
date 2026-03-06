# db/seed_db.py
import pandas as pd
import sqlite3
from db.models import get_connection, create_tables

def _delete_existing(conn, table, tenant, mes):
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table} WHERE tenant_id = ? AND mes = ?", (tenant, mes))
    conn.commit()

def _get_table_columns(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    rows = cur.fetchall()
    # rows: (cid, name, type, notnull, dflt_value, pk)
    return [r[1] for r in rows]

def _add_column_if_missing(conn, table, col, col_type="REAL"):
    existing = _get_table_columns(conn, table)
    if col in existing:
        return
    cur = conn.cursor()
    # SQLite ALTER TABLE ADD COLUMN is limited but fine for adding nullable columns
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
    conn.commit()

def _ensure_table_columns_for_df(conn, table, df):
    """
    Garante que a tabela 'table' tenha todas as colunas presentes em df.
    Tipos: se o nome parecer numérico, cria como REAL; senão TEXT.
    """
    existing = _get_table_columns(conn, table)
    for col in df.columns:
        if col in existing:
            continue
        # heurística simples para tipo
        if col.lower() in {
            "ebitda", "lucro_liquido", "valor_firma", "valor_mercado",
            "patrimonio_liquido", "divida_liquida", "divida_bruta",
            "entradas", "saidas", "saldo", "caixa", "receita", "receita_bruta",
            "investimento", "preco_acao", "numero_papeis", "free_float"
        } or col.lower().endswith(("_pct", "_rate")):
            col_type = "REAL"
        else:
            col_type = "TEXT"
        _add_column_if_missing(conn, table, col, col_type=col_type)

def _upsert_dataframe(conn, table, df):
    """
    Para cada linha do df, remove o registro existente (tenant_id, mes) e insere a linha.
    Antes de inserir, garante que a tabela tenha as colunas do DataFrame.
    """
    # garantir colunas na tabela
    _ensure_table_columns_for_df(conn, table, df)

    for _, row in df.iterrows():
        tenant = row.get("tenant_id")
        mes = row.get("mes")
        if tenant is None or mes is None:
            continue
        _delete_existing(conn, table, tenant, mes)
    # agora append; colunas extras já foram adicionadas à tabela
    df.to_sql(table, conn, if_exists="append", index=False)

def seed_db():
    conn = get_connection()
    create_tables(conn)

    # meses: 2025-01, 2025-02, 2025-03
    tenants = ["clienteA", "clienteB"]
    meses = ["2025-01", "2025-02", "2025-03"]

    # -----------------------------
    # Indicadores Financeiros (Fluxo de Caixa)
    # -----------------------------
    data_fin = {
        "tenant_id": [],
        "mes": [],
        "entradas": [],
        "saidas": [],
        "saldo": [],
        "caixa": []
    }

    base = {
        "clienteA": {
            "entradas": [25000.0, 26000.0, 27000.0],
            "saidas": [18500.0, 18700.0, 19000.0],
            "caixa": [12000.0, 12500.0, 13000.0]
        },
        "clienteB": {
            "entradas": [18000.0, 18500.0, 19000.0],
            "saidas": [14000.0, 14200.0, 14400.0],
            "caixa": [8000.0, 8200.0, 8400.0]
        }
    }

    for tenant in tenants:
        vals = base[tenant]
        for i, mes in enumerate(meses):
            entradas = vals["entradas"][i]
            saidas = vals["saidas"][i]
            saldo = entradas - saidas
            caixa = vals["caixa"][i]
            data_fin["tenant_id"].append(tenant)
            data_fin["mes"].append(mes)
            data_fin["entradas"].append(entradas)
            data_fin["saidas"].append(saidas)
            data_fin["saldo"].append(saldo)
            data_fin["caixa"].append(caixa)

    df_fin = pd.DataFrame(data_fin)

    # -----------------------------
    # DRE Financeira
    # -----------------------------
    data_dre = {
        "tenant_id": [],
        "mes": [],
        "receita_bruta": [],
        "deducoes": [],
        "custo_produto_vendido": [],
        "custo_servico_prestado": [],
        "despesas_vendas": [],
        "despesas_administrativas": [],
        "outras_despesas": [],
        "receitas_financeiras": [],
        "despesas_financeiras": [],
        "imposto_renda": []
    }

    dre_base = {
        "clienteA": {
            "receita_bruta": [250000.0, 255000.0, 260000.0],
            "deducoes": [15000.0, 15200.0, 15400.0],
            "cpv": [80000.0, 82000.0, 84000.0],
            "csp": [20000.0, 20500.0, 21000.0],
            "desp_vendas": [15000.0, 15200.0, 15300.0],
            "desp_admin": [10000.0, 10100.0, 10200.0],
            "outras": [5000.0, 5200.0, 5300.0],
            "rec_fin": [8000.0, 8200.0, 8400.0],
            "desp_fin": [4000.0, 4100.0, 4200.0],
            "ir": [12000.0, 12200.0, 12400.0]
        },
        "clienteB": {
            "receita_bruta": [180000.0, 183000.0, 186000.0],
            "deducoes": [10000.0, 10100.0, 10200.0],
            "cpv": [60000.0, 61000.0, 62000.0],
            "csp": [15000.0, 15200.0, 15400.0],
            "desp_vendas": [12000.0, 12100.0, 12200.0],
            "desp_admin": [8000.0, 8100.0, 8200.0],
            "outras": [4000.0, 4100.0, 4200.0],
            "rec_fin": [5000.0, 5100.0, 5200.0],
            "desp_fin": [3000.0, 3050.0, 3100.0],
            "ir": [9000.0, 9200.0, 9400.0]
        }
    }

    for tenant in tenants:
        vals = dre_base[tenant]
        for i, mes in enumerate(meses):
            data_dre["tenant_id"].append(tenant)
            data_dre["mes"].append(mes)
            data_dre["receita_bruta"].append(vals["receita_bruta"][i])
            data_dre["deducoes"].append(vals["deducoes"][i])
            data_dre["custo_produto_vendido"].append(vals["cpv"][i])
            data_dre["custo_servico_prestado"].append(vals["csp"][i])
            data_dre["despesas_vendas"].append(vals["desp_vendas"][i])
            data_dre["despesas_administrativas"].append(vals["desp_admin"][i])
            data_dre["outras_despesas"].append(vals["outras"][i])
            data_dre["receitas_financeiras"].append(vals["rec_fin"][i])
            data_dre["despesas_financeiras"].append(vals["desp_fin"][i])
            data_dre["imposto_renda"].append(vals["ir"][i])

    df_dre = pd.DataFrame(data_dre)

    # --- calcular EBITDA e Lucro Líquido a partir do DRE ---
    def _to_num_safe(v):
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def compute_ebitda_row(r):
        rb = _to_num_safe(r.get("receita_bruta") or r.get("receita") or 0)
        cpv = _to_num_safe(r.get("custo_produto_vendido") or 0)
        csp = _to_num_safe(r.get("custo_servico_prestado") or 0)
        desp_v = _to_num_safe(r.get("despesas_vendas") or 0)
        desp_a = _to_num_safe(r.get("despesas_administrativas") or 0)
        outras = _to_num_safe(r.get("outras_despesas") or 0)
        return rb - cpv - csp - desp_v - desp_a - outras

    def compute_lucro_liquido_row(r):
        ebitda = compute_ebitda_row(r)
        rec_fin = _to_num_safe(r.get("receitas_financeiras") or 0)
        desp_fin = _to_num_safe(r.get("despesas_financeiras") or 0)
        ir = _to_num_safe(r.get("imposto_renda") or 0)
        return ebitda + rec_fin - desp_fin - ir

    df_dre["ebitda"] = df_dre.apply(compute_ebitda_row, axis=1)
    df_dre["lucro_liquido"] = df_dre.apply(compute_lucro_liquido_row, axis=1)

    # garantir tipos numéricos no DRE
    for col in [
        "receita_bruta", "custo_produto_vendido", "custo_servico_prestado",
        "despesas_vendas", "despesas_administrativas", "outras_despesas",
        "receitas_financeiras", "despesas_financeiras", "imposto_renda",
        "ebitda", "lucro_liquido"
    ]:
        if col in df_dre.columns:
            df_dre[col] = pd.to_numeric(df_dre[col], errors="coerce")

    # --- mapear ebitda/lucro para indicadores_financeiros (df_fin) ---
    for col in ["ebitda", "lucro_liquido"]:
        if col not in df_fin.columns:
            df_fin[col] = None

    if not df_dre.empty:
        for _, r in df_dre.iterrows():
            mask = (df_fin["tenant_id"] == r["tenant_id"]) & (df_fin["mes"] == r["mes"])
            if mask.any():
                df_fin.loc[mask, "ebitda"] = r["ebitda"]
                df_fin.loc[mask, "lucro_liquido"] = r["lucro_liquido"]

    # converter colunas numéricas em df_fin
    for col in ["entradas", "saidas", "saldo", "caixa", "ebitda", "lucro_liquido"]:
        if col in df_fin.columns:
            df_fin[col] = pd.to_numeric(df_fin[col], errors="coerce")

    # persistir indicadores_financeiros e dre_financeiro (garante colunas antes de inserir)
    _upsert_dataframe(conn, "indicadores_financeiros", df_fin)
    _upsert_dataframe(conn, "dre_financeiro", df_dre)

    # -----------------------------
    # Indicadores de Vendas
    # -----------------------------
    data_vendas = {
        "tenant_id": [],
        "mes": [],
        "volume_vendas": []
    }

    vendas_base = {
        "clienteA": {"volume": [50, 52, 55]},
        "clienteB": {"volume": [40, 41, 43]}
    }

    for tenant in tenants:
        vals = vendas_base[tenant]
        for i, mes in enumerate(meses):
            data_vendas["tenant_id"].append(tenant)
            data_vendas["mes"].append(mes)
            data_vendas["volume_vendas"].append(vals["volume"][i])

    df_vendas = pd.DataFrame(data_vendas)
    _upsert_dataframe(conn, "indicadores_vendas", df_vendas)

    # -----------------------------
    # Indicadores Operacionais
    # -----------------------------
    data_op = {
        "tenant_id": [],
        "mes": [],
        "vendas": [],
        "vendedores": [],
        "quantidade": [],
        "producao": []
    }

    op_base = {
        "clienteA": {"prod": [95.0, 95.5, 96.0], "vendedores": [5, 5, 5], "quantidade": [120, 125, 130], "vendas": [50, 52, 55]},
        "clienteB": {"prod": [90.0, 90.5, 91.0], "vendedores": [4, 4, 4], "quantidade": [90, 95, 98], "vendas": [40, 41, 43]}
    }

    for tenant in tenants:
        vals = op_base[tenant]
        for i, mes in enumerate(meses):
            data_op["tenant_id"].append(tenant)
            data_op["mes"].append(mes)
            data_op["vendas"].append(vals["vendas"][i])
            data_op["vendedores"].append(vals["vendedores"][i])
            data_op["quantidade"].append(vals["quantidade"][i])
            data_op["producao"].append(vals["prod"][i])

    df_op = pd.DataFrame(data_op)
    _upsert_dataframe(conn, "indicadores_operacionais", df_op)

    # -----------------------------
    # Indicadores de Marketing
    # -----------------------------
    data_mkt = {
        "tenant_id": [],
        "mes": [],
        "receita": [],
        "investimento": [],
        "leads_gerados": []
    }

    mkt_base = {
        "clienteA": {"receita": [25000.0, 26000.0, 27000.0], "invest": [6000.0, 6200.0, 6400.0], "leads": [200, 210, 220]},
        "clienteB": {"receita": [18000.0, 18500.0, 19000.0], "invest": [4000.0, 4200.0, 4400.0], "leads": [150, 155, 160]}
    }

    for tenant in tenants:
        vals = mkt_base[tenant]
        for i, mes in enumerate(meses):
            data_mkt["tenant_id"].append(tenant)
            data_mkt["mes"].append(mes)
            data_mkt["receita"].append(vals["receita"][i])
            data_mkt["investimento"].append(vals["invest"][i])
            data_mkt["leads_gerados"].append(vals["leads"][i])

    df_mkt = pd.DataFrame(data_mkt)
    _upsert_dataframe(conn, "indicadores_marketing", df_mkt)

    # -----------------------------
    # Indicadores de Clientes
    # -----------------------------
    data_cli = {
        "tenant_id": [],
        "mes": [],
        "clientes_ativos": []
    }

    cli_base = {
        "clienteA": {"ativos": [60, 62, 64]},
        "clienteB": {"ativos": [45, 46, 47]}
    }

    for tenant in tenants:
        vals = cli_base[tenant]
        for i, mes in enumerate(meses):
            data_cli["tenant_id"].append(tenant)
            data_cli["mes"].append(mes)
            data_cli["clientes_ativos"].append(vals["ativos"][i])

    df_cli = pd.DataFrame(data_cli)
    _upsert_dataframe(conn, "indicadores_clientes", df_cli)

    # -----------------------------
    # Dados Contábeis (repetidos por mês para simplificar)
    # -----------------------------
    data_contabil = {
        "tenant_id": [],
        "mes": [],
        "patrimonio_liquido": [],
        "ativos": [],
        "ativo_circulante": [],
        "disponibilidade": [],
        "divida_bruta": [],
        "divida_liquida": [],
        "numero_papeis": [],
        "free_float": [],
        "segmento_listagem": [],
        "tipo_empresa": []
    }

    cont_base = {
        "clienteA": {
            "patrimonio_liquido": 57200.0,
            "ativos": 45121.0,
            "ativo_circulante": 15965.0,
            "disponibilidade": 44560.0,
            "divida_bruta": 16298.0,
            "divida_liquida": 11842.0,
            "numero_papeis": 13534,
            "free_float": 0.989,
            "segmento_listagem": "Novo Mercado",
            "tipo_empresa": "aberta"
        },
        "clienteB": {
            "patrimonio_liquido": 32000.0,
            "ativos": 21000.0,
            "ativo_circulante": 75000.0,
            "disponibilidade": 25000.0,
            "divida_bruta": 80000.0,
            "divida_liquida": 5500.0,
            "numero_papeis": None,
            "free_float": None,
            "segmento_listagem": None,
            "tipo_empresa": "fechada"
        }
    }

    for tenant in tenants:
        vals = cont_base[tenant]
        for mes in meses:
            data_contabil["tenant_id"].append(tenant)
            data_contabil["mes"].append(mes)
            data_contabil["patrimonio_liquido"].append(vals["patrimonio_liquido"])
            data_contabil["ativos"].append(vals["ativos"])
            data_contabil["ativo_circulante"].append(vals["ativo_circulante"])
            data_contabil["disponibilidade"].append(vals["disponibilidade"])
            data_contabil["divida_bruta"].append(vals["divida_bruta"])
            data_contabil["divida_liquida"].append(vals["divida_liquida"])
            data_contabil["numero_papeis"].append(vals["numero_papeis"])
            data_contabil["free_float"].append(vals["free_float"])
            data_contabil["segmento_listagem"].append(vals["segmento_listagem"])
            data_contabil["tipo_empresa"].append(vals["tipo_empresa"])

    df_cont = pd.DataFrame(data_contabil)

    # --- garantir colunas numéricas e calcular valor_firma ---
    for col in ["patrimonio_liquido", "divida_liquida", "divida_bruta", "ativos", "disponibilidade"]:
        if col in df_cont.columns:
            df_cont[col] = pd.to_numeric(df_cont[col], errors="coerce")

    if "valor_firma" not in df_cont.columns:
        df_cont["valor_firma"] = None

    for idx, r in df_cont.iterrows():
        pl = _to_num_safe(r.get("patrimonio_liquido"))
        div_liq = _to_num_safe(r.get("divida_liquida"))
        if div_liq == 0:
            div_liq = _to_num_safe(r.get("divida_bruta"))
        df_cont.at[idx, "valor_firma"] = pl + div_liq

    df_cont["valor_firma"] = pd.to_numeric(df_cont["valor_firma"], errors="coerce")

    _upsert_dataframe(conn, "dados_contabeis", df_cont)

    conn.close()
    print("🌱 Dados fictícios para 3 meses inseridos com sucesso!")

if __name__ == "__main__":
    seed_db()