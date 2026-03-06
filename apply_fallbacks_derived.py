# apply_fallbacks_derived.py
import math
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np
from app.dashboards.utils_calc import calc_all_kpis

DB = Path("streamdash.db")

def safe_div(a, b):
    try:
        if a is None or b is None:
            return np.nan
        a = float(a)
        b = float(b)
        if math.isfinite(a) and math.isfinite(b) and b != 0:
            return a / b
    except Exception:
        pass
    return np.nan

def apply_fallbacks(derived):
    """
    Normaliza tipos, garante colunas esperadas e aplica fallbacks para KPIs
    estratégicos (margem líquida, ROI, ROE, EBITDA, CAGR, Dívida/EBITDA).
    """
    if derived is None:
        return None

    # copia para não alterar original por referência
    df = derived.copy()

    # garantir colunas existam e normalizar nomes alternativos
    expected_cols = [
        "valor_mercado", "valor_firma", "patrimonio_liquido", "ebitda",
        "lucro_liquido", "numero_papeis", "free_float", "cagr_receitas",
        "vendas", "vendedores", "producao", "quantidade", "custo_total",
        "receita", "receita_bruta", "investimento", "leads_gerados",
        "clientes_ativos", "divida_liquida", "divida_bruta", "preco_acao",
        "p_vp", "pl", "ev_ebitda", "peg_ratio", "produtividade", "custo_unidade",
        "taxa_engajamento", "taxa_retencao", "nps", "roi", "roe", "margem_liquida",
        "divida_ebitda"
    ]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = np.nan

    # converter colunas numéricas para float coerente
    numeric_cols = [
        "valor_mercado", "valor_firma", "patrimonio_liquido", "ebitda",
        "lucro_liquido", "numero_papeis", "free_float", "cagr_receitas",
        "vendas", "vendedores", "producao", "quantidade", "custo_total",
        "receita", "receita_bruta", "investimento", "leads_gerados",
        "clientes_ativos", "divida_liquida", "divida_bruta", "preco_acao"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # aliases: unificar receita_bruta -> receita quando apropriado
    if "receita_bruta" in df.columns and "receita" not in df.columns:
        df["receita"] = df["receita_bruta"]

    # fallback p_vp: prefer P / VPA (valor_mercado / patrimonio_liquido) se numero_papeis/price não disponíveis
    def compute_p_vp(row):
        if pd.notna(row.get("p_vp")):
            return row.get("p_vp")
        vm = row.get("valor_mercado")
        patr = row.get("patrimonio_liquido")
        if pd.notna(vm) and pd.notna(patr) and patr != 0:
            return safe_div(vm, patr)
        price = row.get("preco_acao") if "preco_acao" in row.index else None
        npap = row.get("numero_papeis")
        if pd.notna(price) and pd.notna(npap) and npap != 0:
            return safe_div(price * npap, patr) if pd.notna(patr) and patr != 0 else np.nan
        return np.nan

    # fallback pl: valor_mercado / lucro_liquido
    def compute_pl(row):
        if pd.notna(row.get("pl")):
            return row.get("pl")
        vm = row.get("valor_mercado")
        lucro = row.get("lucro_liquido")
        return safe_div(vm, lucro)

    # fallback ev_ebitda: valor_firma / ebitda
    def compute_ev_ebitda(row):
        if pd.notna(row.get("ev_ebitda")):
            return row.get("ev_ebitda")
        vf = row.get("valor_firma")
        eb = row.get("ebitda")
        return safe_div(vf, eb)

    # fallback peg_ratio: pl / cagr_receitas (cagr em decimal)
    def compute_peg(row):
        if pd.notna(row.get("peg_ratio")):
            return row.get("peg_ratio")
        pl = compute_pl(row) if pd.isna(row.get("pl")) else row.get("pl")
        cagr = row.get("cagr_receitas")
        if pd.notna(pl) and pd.notna(cagr) and cagr != 0:
            return safe_div(pl, cagr)
        return np.nan

    # produtividade: prefer coluna; senão producao / vendedores ou vendas / vendedores
    def compute_produtividade(row):
        if pd.notna(row.get("produtividade")):
            return row.get("produtividade")
        vendedores = row.get("vendedores")
        producao = row.get("producao")
        vendas = row.get("vendas")
        if pd.notna(vendedores) and vendedores != 0:
            if pd.notna(producao):
                return safe_div(producao, vendedores)
            if pd.notna(vendas):
                return safe_div(vendas, vendedores)
        return np.nan

    # custo_unidade: prefer coluna; senão custo_total / quantidade
    def compute_custo_unidade(row):
        if pd.notna(row.get("custo_unidade")):
            return row.get("custo_unidade")
        custo_total = row.get("custo_total")
        quantidade = row.get("quantidade")
        return safe_div(custo_total, quantidade)

    # taxa_engajamento: fallback simples = leads_gerados / receita (se fizer sentido) ou NaN
    def compute_taxa_engajamento(row):
        if pd.notna(row.get("taxa_engajamento")):
            return row.get("taxa_engajamento")
        leads = row.get("leads_gerados")
        receita = row.get("receita")
        if pd.notna(leads) and pd.notna(receita) and receita != 0:
            return safe_div(leads, receita)
        return np.nan

    # taxa_retencao, nps: sem dados, mantemos NaN; but try simple proxy: change in clientes_ativos
    def compute_taxa_retencao(row, next_row=None):
        if pd.notna(row.get("taxa_retencao")):
            return row.get("taxa_retencao")
        return np.nan

    def compute_nps(row):
        return row.get("nps") if pd.notna(row.get("nps")) else np.nan

    # apply per-row for derived fallbacks
    df["p_vp"] = df.apply(compute_p_vp, axis=1)
    df["pl"] = df.apply(compute_pl, axis=1)
    df["ev_ebitda"] = df.apply(compute_ev_ebitda, axis=1)
    df["peg_ratio"] = df.apply(compute_peg, axis=1)
    df["produtividade"] = df.apply(compute_produtividade, axis=1)
    df["custo_unidade"] = df.apply(compute_custo_unidade, axis=1)
    df["taxa_engajamento"] = df.apply(compute_taxa_engajamento, axis=1)
    df["nps"] = df.apply(compute_nps, axis=1)

    # taxa_retencao proxy: compute month-over-month retention per tenant from clientes_ativos
    if "clientes_ativos" in df.columns:
        df = df.sort_values(["tenant_id", "mes"])
        df["taxa_retencao"] = np.nan
        for tenant, g in df.groupby("tenant_id"):
            g = g.sort_values("mes")
            prev = None
            for idx, row in g.iterrows():
                cur_clients = row.get("clientes_ativos")
                if prev is not None and pd.notna(prev) and pd.notna(cur_clients):
                    if prev != 0:
                        df.at[idx, "taxa_retencao"] = safe_div(cur_clients, prev)
                    else:
                        df.at[idx, "taxa_retencao"] = np.nan
                prev = cur_clients

    # --- KPI fallbacks adicionais (margem_liquida, roe, roi, divida_ebitda, cagr_receitas) ---
    # margem_liquida: lucro_liquido / receita
    if "margem_liquida" not in df.columns:
        df["margem_liquida"] = np.nan
    for idx, row in df.iterrows():
        if pd.isna(row.get("margem_liquida")):
            lucro = row.get("lucro_liquido")
            rev = row.get("receita")
            if pd.notna(lucro) and pd.notna(rev) and rev != 0:
                df.at[idx, "margem_liquida"] = safe_div(lucro, rev)

    # roe: lucro_liquido_total / patrimonio_liquido (se lucro for série, usar soma por tenant/mes não-serial aqui assume linha)
    if "roe" not in df.columns:
        df["roe"] = np.nan
    for idx, row in df.iterrows():
        if pd.isna(row.get("roe")):
            lucro = row.get("lucro_liquido")
            patr = row.get("patrimonio_liquido")
            if pd.notna(lucro) and pd.notna(patr) and patr != 0:
                df.at[idx, "roe"] = safe_div(lucro, patr)

    # roi: prefer lucro / investimento, senão lucro / patrimonio_liquido
    if "roi" not in df.columns:
        df["roi"] = np.nan
    for idx, row in df.iterrows():
        if pd.isna(row.get("roi")):
            lucro = row.get("lucro_liquido")
            invest = row.get("investimento")
            patr = row.get("patrimonio_liquido")
            if pd.notna(lucro) and pd.notna(invest) and invest != 0:
                df.at[idx, "roi"] = safe_div(lucro, invest)
            elif pd.notna(lucro) and pd.notna(patr) and patr != 0:
                df.at[idx, "roi"] = safe_div(lucro, patr)

    # divida_ebitda: divida_liquida / ebitda (usar divida_bruta se divida_liquida ausente)
    if "divida_ebitda" not in df.columns:
        df["divida_ebitda"] = np.nan
    for idx, row in df.iterrows():
        if pd.isna(row.get("divida_ebitda")):
            div_liq = row.get("divida_liquida")
            if pd.isna(div_liq) and pd.notna(row.get("divida_bruta")):
                div_liq = row.get("divida_bruta")
            eb = row.get("ebitda")
            if pd.notna(div_liq) and pd.notna(eb) and eb != 0:
                df.at[idx, "divida_ebitda"] = safe_div(div_liq, eb)

    # cagr_receitas: se houver série por tenant/mes, tentar calcular CAGR simples (last/first) por grupo
    if "cagr_receitas" not in df.columns:
        df["cagr_receitas"] = np.nan
    try:
        if "tenant_id" in df.columns and "mes" in df.columns and ("receita" in df.columns or "receita_bruta" in df.columns):
            grp = df.sort_values(["tenant_id", "mes"]).groupby("tenant_id")
            for tenant, g in grp:
                rev_col = "receita" if "receita" in g.columns else "receita_bruta"
                s = pd.to_numeric(g[rev_col], errors="coerce").dropna()
                if s.size >= 2:
                    first = float(s.iloc[0])
                    last = float(s.iloc[-1])
                    # assumir meses como períodos; converter para anos aproximados
                    n_periods = s.size - 1
                    years = n_periods / 12.0 if n_periods > 0 else 0
                    if first > 0 and last > 0 and years > 0:
                        cagr = (last / first) ** (1.0 / years) - 1.0
                        # aplicar cagr para as linhas desse tenant (fallback simples)
                        df.loc[df["tenant_id"] == tenant, "cagr_receitas"] = cagr
    except Exception:
        pass

    # ensure numeric types where appropriate (final pass)
    final_numeric = [
        "p_vp", "ev_ebitda", "pl", "peg_ratio", "produtividade", "custo_unidade",
        "taxa_engajamento", "taxa_retencao", "nps", "margem_liquida", "roe",
        "roi", "divida_ebitda", "ebitda", "lucro_liquido", "cagr_receitas"
    ]
    for col in final_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

def main():
    # carregar DFs a partir do DB como o app faria
    conn = sqlite3.connect(str(DB))
    tables = {
      "dre": "dre_financeiro",
      "contabeis": "dados_contabeis",
      "vendas": "indicadores_vendas",
      "finance": "indicadores_financeiros",
      "marketing": "indicadores_marketing",
      "operacional": "indicadores_operacionais",
      "clientes": "indicadores_clientes"
    }
    dfs = {}
    for k, t in tables.items():
        try:
            dfs[k] = pd.read_sql_query(f"SELECT * FROM {t}", conn)
        except Exception:
            dfs[k] = pd.DataFrame()
    conn.close()

    res = calc_all_kpis(dfs)
    derived = res.get("derived") if isinstance(res, dict) else None
    if derived is None:
        print("calc_all_kpis did not return derived")
        return

    derived_fixed = apply_fallbacks(derived)
    pd.set_option("display.max_columns", None)
    print("\n=== derived head (fixed) ===")
    print(derived_fixed.head(10).to_string(index=False))
    print("\n=== derived null counts (fixed) ===")
    print(derived_fixed.isna().sum().to_string())

if __name__ == "__main__":
    main()