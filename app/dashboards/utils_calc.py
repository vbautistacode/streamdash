# app/dashboards/utils_calc.py
"""
Cálculos derivados e compat shim.

Principais responsabilidades:
- padronizar nomes de input (aceitar formas legadas)
- calcular KPIs por tenant_id + mes quando possível
- retornar um dict com 'derived' (DataFrame) e também um dicionário sumarizado quando pedido
- fornecer calc_all_kpis(dfs) e compat calc_estrategicos_from_dre(dfs)
"""

from typing import Dict, Any, Optional
import math
import numpy as np
import pandas as pd

# -----------------------------
# Utilitários internos
# -----------------------------
def _safe_div(num, den):
    try:
        if den is None or den == 0 or (isinstance(den, float) and math.isnan(den)):
            return np.nan
        return float(num) / float(den)
    except Exception:
        return np.nan

def _to_float_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _sum_col(df: pd.DataFrame, col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return float(_to_float_series(df[col]).sum())

def _mean_col(df: pd.DataFrame, col: str) -> Optional[float]:
    if df is None or df.empty or col not in df.columns:
        return None
    vals = _to_float_series(df[col]).dropna()
    return float(vals.mean()) if not vals.empty else None

# Padronização de chaves/nomes de df no input
def _get_dfs(dfs: Dict[str, Optional[pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
    # aceita várias keys legadas
    mapping = {
        "dre": ["dre", "dre_financeiro"],
        "finance": ["financeiros", "finance", "indicadores_financeiros"],
        "vendas": ["vendas", "indicadores_vendas"],
        "operacional": ["operacionais", "indicadores_operacionais"],
        "marketing": ["marketing", "indicadores_marketing"],
        "clientes": ["clientes", "indicadores_clientes"],
        "contabeis": ["contabeis", "dados_contabeis"]
    }
    res = {}
    for key, candidates in mapping.items():
        found = None
        for c in candidates:
            if c in dfs and dfs[c] is not None:
                found = dfs[c]
                break
        res[key] = found.copy() if isinstance(found, pd.DataFrame) else pd.DataFrame()
    return res

# -----------------------------
# Cálculos auxiliares por grupo (tenant+mes)
# -----------------------------
def _compute_for_group(group: Dict[str, pd.DataFrame], tenant: str, mes: str) -> Dict[str, Any]:
    dre = group["dre"]
    finance = group["finance"]
    vendas = group["vendas"]
    oper = group["operacional"]
    mkt = group["marketing"]
    cli = group["clientes"]
    cont = group["contabeis"]

    out: Dict[str, Any] = {"tenant_id": tenant, "mes": mes}

    # --- Financeiros / DRE ---
    receita_bruta = _sum_col(dre, "receita_bruta")
    deducoes = _sum_col(dre, "deducoes")
    receita_liquida = receita_bruta - deducoes if not (math.isnan(receita_bruta) or math.isnan(deducoes)) else np.nan
    cpv = _sum_col(dre, "custo_produto_vendido") or _sum_col(dre, "cpv")
    csp = _sum_col(dre, "custo_servico_prestado")
    desp_vendas = _sum_col(dre, "despesas_vendas")
    desp_admin = _sum_col(dre, "despesas_administrativas")
    outras = _sum_col(dre, "outras_despesas")
    despesas_operacionais = desp_vendas + desp_admin + outras

    lucro_bruto = receita_liquida - (cpv + csp) if not math.isnan(receita_liquida) else np.nan
    ebitda = lucro_bruto - despesas_operacionais if not math.isnan(lucro_bruto) else np.nan
    out["ebitda"] = float(ebitda) if not (isinstance(ebitda, float) and math.isnan(ebitda)) else np.nan

    rec_fin = _sum_col(dre, "receitas_financeiras")
    desp_fin = _sum_col(dre, "despesas_financeiras")
    resultado_fin = rec_fin - desp_fin
    ir = _sum_col(dre, "imposto_renda")
    lucro_operacional = lucro_bruto - despesas_operacionais if not math.isnan(lucro_bruto) else np.nan
    lucro_antes_ir = lucro_operacional + resultado_fin if not math.isnan(lucro_operacional) else np.nan
    lucro_liquido = lucro_antes_ir - ir if not math.isnan(lucro_antes_ir) else np.nan
    out["lucro_liquido"] = float(lucro_liquido) if not (isinstance(lucro_liquido, float) and math.isnan(lucro_liquido)) else np.nan

    out["margem_bruta"] = _safe_div(lucro_bruto, receita_liquida) if not math.isnan(receita_liquida) else np.nan
    out["margem_operacional"] = _safe_div(lucro_operacional, receita_liquida) if not math.isnan(receita_liquida) else np.nan
    out["margem_liquida"] = _safe_div(lucro_liquido, receita_liquida) if not math.isnan(receita_liquida) else np.nan

    # --- Contábeis (último disponível dentro do mesmo mes se houver) ---
    patrimonio = None
    divida_liq = None
    divida_bruta = None
    valor_mercado = None
    valor_firma = None
    numero_papeis = None
    free_float = None
    if not cont.empty:
        # preferir registros exatamente do mes; senão último do tenant
        cont_tenant_mes = cont[(cont.get("tenant_id") == tenant) & (cont.get("mes") == mes)]
        if not cont_tenant_mes.empty:
            last = cont_tenant_mes.iloc[-1]
        else:
            # último por tenant
            cont_tenant = cont[cont.get("tenant_id") == tenant] if "tenant_id" in cont.columns else cont
            last = cont_tenant.sort_values("mes").iloc[-1] if not cont_tenant.empty and "mes" in cont_tenant.columns else cont_tenant.iloc[-1] if not cont_tenant.empty else None
        if last is not None:
            patrimonio = last.get("patrimonio_liquido") if "patrimonio_liquido" in last.index else None
            divida_liq = last.get("divida_liquida") if "divida_liquida" in last.index else None
            divida_bruta = last.get("divida_bruta") if "divida_bruta" in last.index else None
            valor_mercado = last.get("valor_mercado") if "valor_mercado" in last.index else None
            valor_firma = last.get("valor_firma") if "valor_firma" in last.index else None
            numero_papeis = last.get("numero_papeis") if "numero_papeis" in last.index else None
            free_float = last.get("free_float") if "free_float" in last.index else None

    # dívidas / ebitda
    debt_for_calc = divida_liq if divida_liq not in (None, np.nan) else divida_bruta
    out["divida_ebitda"] = _safe_div(debt_for_calc, ebitda) if not (isinstance(ebitda, float) and math.isnan(ebitda)) else np.nan

    # ROE / P/VPA / EV/EBITDA / P/L
    out["roe"] = _safe_div(lucro_liquido, patrimonio)
    out["p_vp"] = _safe_div(valor_mercado, patrimonio)
    out["ev_ebitda"] = _safe_div(valor_firma, ebitda)
    out["pl"] = _safe_div(valor_mercado, lucro_liquido)

    # cagr de receitas: se dre tem mais de 1 mês, tentar localmente (mas o LTM ideal fica para etapa seguinte)
    out["cagr_receitas"] = np.nan  # preenchido em calc_all_kpis agrupado

    # PEG (placeholder)
    out["peg_ratio"] = np.nan

    # ROI (financeiro simples)
    entradas_sum = _sum_col(finance, "entradas")
    saidas_sum = _sum_col(finance, "saidas")
    out["roi"] = _safe_div((entradas_sum - saidas_sum), saidas_sum) if saidas_sum else np.nan

    # --- Vendas: ticket, taxa de conversao, churn, ltv ---
    # ticket medio: preferir coluna; fallback receita / volume_vendas (agregado)
    ticket_col_mean = _mean_col(vendas, "ticket_medio")
    if ticket_col_mean is not None:
        ticket_medio = ticket_col_mean
    else:
        # receita possível em marketing ou financeiro
        receita_from_mkt = _sum_col(mkt, "receita") if "receita" in mkt.columns else 0.0
        receita_from_fin = entradas_sum
        total_revenue = receita_from_mkt + receita_from_fin
        volume = _sum_col(vendas, "volume_vendas")
        ticket_medio = _safe_div(total_revenue, volume) if volume else np.nan
    out["ticket_medio"] = float(ticket_medio) if not (isinstance(ticket_medio, float) and math.isnan(ticket_medio)) else np.nan

    # taxa_conversao: preferir coluna; fallback conv_total = clientes / visitas or clientes/ leads
    taxa_conv = _mean_col(vendas, "taxa_conversao")
    if taxa_conv is None:
        visitas = _sum_col(mkt, "visitas") if "visitas" in mkt.columns else 0.0
        leads = _sum_col(mkt, "leads_gerados") if "leads_gerados" in mkt.columns else _sum_col(vendas, "leads_gerados")
        clientes_count = _sum_col(cli, "clientes_ativos") if "clientes_ativos" in cli.columns else _sum_col(vendas, "clientes_ativos")
        # conversao visitantes->clientes
        conv_vis_leads = _safe_div(leads, visitas) if visitas else np.nan
        conv_leads_cli = _safe_div(clientes_count, leads) if leads else np.nan
        conv_total = _safe_div(clientes_count, visitas) if visitas else np.nan
        taxa_conv = conv_total if not math.isnan(conv_total) else (conv_leads_cli if not math.isnan(conv_leads_cli) else np.nan)
    out["taxa_conversao"] = float(taxa_conv) if not (isinstance(taxa_conv, float) and math.isnan(taxa_conv)) else np.nan

    # churn_rate: prefer cli table; se for série, calcular usando first/last
    churn_val = _mean_col(cli, "churn_rate")
    if churn_val is None:
        # tentativa por série (clientes ativos ao longo do mes)
        if not cli.empty and "clientes_ativos" in cli.columns and "mes" in cli.columns:
            try:
                cli_sorted = cli.sort_values("mes")
                start = _to_float_series(cli_sorted["clientes_ativos"]).dropna().iloc[0] if not cli_sorted.empty else np.nan
                end = _to_float_series(cli_sorted["clientes_ativos"]).dropna().iloc[-1] if not cli_sorted.empty else np.nan
                churn_calc = _safe_div((start - end), start) if start and start != 0 else np.nan
                churn_val = churn_calc if not math.isnan(churn_calc) else np.nan
            except Exception:
                churn_val = np.nan
        else:
            churn_val = _mean_col(vendas, "churn_rate")
    out["churn_rate"] = float(churn_val) if not (isinstance(churn_val, float) and math.isnan(churn_val)) else np.nan

    # LTV: prefer coluna; fallback receita_total / clientes
    ltv_val = _mean_col(vendas, "ltv")
    if ltv_val is None:
        receita_total_vendas = _sum_col(vendas, "receita") if "receita" in vendas.columns else 0.0
        clientes_count = _sum_col(cli, "clientes_ativos") if "clientes_ativos" in cli.columns else 0.0
        ltv_calc = _safe_div(receita_total_vendas, clientes_count) if clientes_count else np.nan
        ltv_val = ltv_calc
    out["ltv"] = float(ltv_val) if not (isinstance(ltv_val, float) and math.isnan(ltv_val)) else np.nan

    # --- Operacionais ---
    out["produtividade"] = float(_mean_col(oper, "produtividade") or _mean_col(oper, "producao") or np.nan)
    out["custo_unidade"] = float(_mean_col(oper, "custo_unidade") or np.nan)

    # --- Marketing ---
    cac_val = _mean_col(mkt, "cac")
    if cac_val is None:
        investimento = _sum_col(mkt, "investimento")
        leads_sum = _sum_col(mkt, "leads_gerados")
        cac_calc = _safe_div(investimento, leads_sum) if leads_sum else np.nan
        cac_val = cac_calc
    out["cac"] = float(cac_val) if not (isinstance(cac_val, float) and math.isnan(cac_val)) else np.nan
    out["taxa_engajamento"] = float(_mean_col(mkt, "taxa_engajamento") or np.nan)
    investimento_sum = _sum_col(mkt, "investimento")
    leads_sum = _sum_col(mkt, "leads_gerados")
    out["custo_por_lead"] = float(_safe_div(investimento_sum, leads_sum) if leads_sum else np.nan)

    # --- Clientes ---
    out["taxa_retencao"] = float(_mean_col(cli, "taxa_retencao") or np.nan)
    out["nps"] = float(_mean_col(cli, "nps") or np.nan)

    # --- Mercado / contábeis expostos ---
    out["valor_mercado"] = float(valor_mercado) if valor_mercado not in (None, np.nan) else np.nan
    out["valor_firma"] = float(valor_firma) if valor_firma not in (None, np.nan) else np.nan
    try:
        out["numero_papeis"] = int(float(numero_papeis)) if (numero_papeis is not None and str(numero_papeis) != '' and not (isinstance(numero_papeis, float) and __import__('math').isnan(numero_papeis))) else np.nan
    except Exception:
        out["numero_papeis"] = np.nan
    out["free_float"] = float(free_float) if free_float not in (None, "", np.nan) else np.nan

    # liquidez corrente (simplificação defensiva)
    liq = np.nan
    try:
        if last is not None and "ativo_circulante" in last.index and "divida_bruta" in last.index:
            liq = _safe_div(last.get("ativo_circulante"), last.get("divida_bruta"))
    except Exception:
        liq = np.nan
    out["liquidez_corrente"] = float(liq) if not (isinstance(liq, float) and math.isnan(liq)) else np.nan

    return out

# -----------------------------
# Função principal: calcula derived DataFrame e sumariza
# -----------------------------
def calc_all_kpis(dfs: Dict[str, Optional[pd.DataFrame]]) -> Dict[str, Any]:
    """
    Recebe dict de DataFrames (pode conter chaves legadas).
    Retorna dict com:
      - 'derived': dataframe com linhas por tenant_id + mes e colunas de indicadores
      - outras chaves opcionais (agregados globais)
    """
    # padroniza dicionário de dataframes
    standardized = _get_dfs(dfs)
    dre = standardized["dre"]
    finance = standardized["finance"]
    vendas = standardized["vendas"]
    oper = standardized["operacional"]
    mkt = standardized["marketing"]
    cli = standardized["clientes"]
    cont = standardized["contabeis"]

    # identificar pares tenant+mes existentes nas fontes (união)
    tenants = set()
    pairs = set()
    for df in (dre, finance, vendas, oper, mkt, cli, cont):
        if df is None or df.empty:
            continue
        if "tenant_id" in df.columns and "mes" in df.columns:
            for t, m in zip(df["tenant_id"].astype(str), df["mes"].astype(str)):
                pairs.add((t, m))
                tenants.add(t)

    # se nenhum par, tentar agrupar por tenant apenas (último mes)
    if not pairs:
        # fallback: pegar últimos meses por cont ou finance
        fallback_df = cont if not cont.empty else finance if not finance.empty else pd.DataFrame()
        if not fallback_df.empty and "tenant_id" in fallback_df.columns:
            for t in fallback_df["tenant_id"].unique():
                # determine mes
                sub = fallback_df[fallback_df["tenant_id"] == t]
                mes = sub["mes"].astype(str).max() if "mes" in sub.columns else ""
                pairs.add((t, mes))

    rows = []
    # para cálculo de CAGR global por tenant, agrupamos dre por tenant+mes (se possível)
    dre_grouped = dre.copy() if not dre.empty else pd.DataFrame()
    if not dre_grouped.empty:
        dre_grouped["mes"] = dre_grouped["mes"].astype(str)
    # iterar pares e calcular
    for tenant, mes in pairs:
        # construir subframes por tenant+mes para cálculo local
        sub = {
            "dre": dre[(dre.get("tenant_id").astype(str) == str(tenant)) & (dre.get("mes").astype(str) == str(mes))] if not dre.empty and "tenant_id" in dre.columns and "mes" in dre.columns else (dre[dre.get("tenant_id").astype(str) == str(tenant)] if not dre.empty and "tenant_id" in dre.columns else pd.DataFrame()),
            "finance": finance[(finance.get("tenant_id").astype(str) == str(tenant)) & (finance.get("mes").astype(str) == str(mes))] if not finance.empty and "tenant_id" in finance.columns and "mes" in finance.columns else (finance[finance.get("tenant_id").astype(str) == str(tenant)] if not finance.empty and "tenant_id" in finance.columns else pd.DataFrame()),
            "vendas": vendas[(vendas.get("tenant_id").astype(str) == str(tenant)) & (vendas.get("mes").astype(str) == str(mes))] if not vendas.empty and "tenant_id" in vendas.columns and "mes" in vendas.columns else (vendas[vendas.get("tenant_id").astype(str) == str(tenant)] if not vendas.empty and "tenant_id" in vendas.columns else pd.DataFrame()),
            "operacional": oper[(oper.get("tenant_id").astype(str) == str(tenant)) & (oper.get("mes").astype(str) == str(mes))] if not oper.empty and "tenant_id" in oper.columns and "mes" in oper.columns else (oper[oper.get("tenant_id").astype(str) == str(tenant)] if not oper.empty and "tenant_id" in oper.columns else pd.DataFrame()),
            "marketing": mkt[(mkt.get("tenant_id").astype(str) == str(tenant)) & (mkt.get("mes").astype(str) == str(mes))] if not mkt.empty and "tenant_id" in mkt.columns and "mes" in mkt.columns else (mkt[mkt.get("tenant_id").astype(str) == str(tenant)] if not mkt.empty and "tenant_id" in mkt.columns else pd.DataFrame()),
            "clientes": cli[(cli.get("tenant_id").astype(str) == str(tenant)) & (cli.get("mes").astype(str) == str(mes))] if not cli.empty and "tenant_id" in cli.columns and "mes" in cli.columns else (cli[cli.get("tenant_id").astype(str) == str(tenant)] if not cli.empty and "tenant_id" in cli.columns else pd.DataFrame()),
            "contabeis": cont if not cont.empty else pd.DataFrame()
        }
        row = _compute_for_group(sub, tenant, mes)
        rows.append(row)

    derived = pd.DataFrame(rows)
    # calcular CAGR por tenant usando dre_grouped quando possível (LTM/years aprox)
    cagr_map = {}
    if not dre_grouped.empty:
        for tenant in derived["tenant_id"].unique():
            t_dre = dre_grouped[dre_grouped["tenant_id"].astype(str) == str(tenant)]
            if t_dre.empty:
                cagr_map[tenant] = np.nan
                continue
            monthly = t_dre.groupby("mes")["receita_bruta"].sum().sort_index()
            if len(monthly) >= 2:
                first = monthly.iloc[0]
                last = monthly.iloc[-1]
                n_months = monthly.size
                years = n_months / 12.0
                try:
                    if first > 0 and years > 0:
                        cagr = (last / first) ** (1.0 / years) - 1.0
                    else:
                        cagr = np.nan
                except Exception:
                    cagr = np.nan
            else:
                cagr = np.nan
            cagr_map[tenant] = cagr
    # aplicar cagr e peg_ratio
    if not derived.empty:
        derived["cagr_receitas"] = derived["tenant_id"].map(cagr_map).astype(float)
        # peg_ratio = pl / cagr, defensivo
        derived["peg_ratio"] = derived.apply(lambda r: _safe_div(r.get("pl"), r.get("cagr_receitas")) if not (r.get("cagr_receitas") in (None, np.nan)) else np.nan, axis=1)

    # garantir colunas esperadas e tipos coerentes
    expected = [
        "tenant_id", "mes", "ebitda", "lucro_liquido", "margem_bruta", "margem_operacional", "margem_liquida",
        "divida_ebitda", "roe", "p_vp", "ev_ebitda", "pl", "cagr_receitas", "peg_ratio", "roi",
        "ticket_medio", "taxa_conversao", "churn_rate", "ltv",
        "produtividade", "custo_unidade", "cac", "taxa_engajamento", "custo_por_lead",
        "taxa_retencao", "nps", "valor_mercado", "valor_firma", "numero_papeis", "free_float", "liquidez_corrente"
    ]
    for col in expected:
        if col not in derived.columns:
            derived[col] = np.nan

    # converter numeric coerente
    for col in derived.columns:
        if col not in ("tenant_id", "mes"):
            derived[col] = pd.to_numeric(derived[col], errors="coerce")

    # montar retorno: derived df + sumarização opcional
    out: Dict[str, Any] = {"derived": derived}

    # sumarizar por tenant último registro (útil quando chamada por legacy)
    try:
        summary = {}
        for tenant in derived["tenant_id"].unique():
            last_row = derived[derived["tenant_id"] == tenant].sort_values("mes").iloc[-1]
            summary[tenant] = {k: (None if pd.isna(last_row.get(k)) else last_row.get(k)) for k in expected if k not in ("tenant_id", "mes")}
        out["summary"] = summary
    except Exception:
        out["summary"] = {}

    return out

# -----------------------------
# Compat shim antigo
# -----------------------------
try:
    calc_all = globals().get("calc_all_kpis") or globals().get("calc_all")
except Exception:
    calc_all = None

def calc_estrategicos_from_dre(dfs):
    """
    Compat wrapper usado por db.models.
    Delegates to calc_all_kpis and returns summary for legacy callers.
    """
    if callable(calc_all):
        try:
            res = calc_all(dfs)
            # legacy espera um dict com chaves de métricas (por tenant talvez)
            # se res contém "summary" devolvemos o summary do tenant principal (first)
            if isinstance(res, dict) and "summary" in res:
                # se caller forneceu um único tenant no dfs, retornamos summary para esse tenant
                # fallback: retorna summary completo
                return res["summary"]
            return res
        except Exception:
            pass

    # fallback defensivo: tentar calcular ebitda/margem/patrimonio mínimo
    try:
        dre = dfs.get("dre") if isinstance(dfs, dict) else (dfs if isinstance(dfs, pd.DataFrame) else pd.DataFrame())
        cont = dfs.get("contabeis") if isinstance(dfs, dict) else pd.DataFrame()
        receita = dre["receita_bruta"].sum() if ("receita_bruta" in dre.columns and not dre.empty) else 0.0
        deducoes = dre["deducoes"].sum() if ("deducoes" in dre.columns and not dre.empty) else 0.0
        receita_liq = receita - deducoes
        cpv = dre["custo_produto_vendido"].sum() if ("custo_produto_vendido" in dre.columns and not dre.empty) else 0.0
        csp = dre["custo_servico_prestado"].sum() if ("custo_servico_prestado" in dre.columns and not dre.empty) else 0.0
        desp_vendas = dre["despesas_vendas"].sum() if ("despesas_vendas" in dre.columns and not dre.empty) else 0.0
        desp_admin = dre["despesas_administrativas"].sum() if ("despesas_administrativas" in dre.columns and not dre.empty) else 0.0
        outras = dre["outras_despesas"].sum() if ("outras_despesas" in dre.columns and not dre.empty) else 0.0
        lucro_bruto = receita_liq - (cpv + csp)
        ebitda = lucro_bruto - (desp_vendas + desp_admin + outras)
        patrimonio = None
        if cont is not None and not cont.empty and "patrimonio_liquido" in cont.columns:
            try:
                patrimonio = cont.sort_values("mes").iloc[-1]["patrimonio_liquido"]
            except Exception:
                patrimonio = cont.iloc[-1].get("patrimonio_liquido")
        return {
            "ebitda": float(ebitda) if ebitda is not None else np.nan,
            "margem_liquida": float((ebitda / receita_liq)) if (receita_liq and receita_liq != 0) else np.nan,
            "patrimonio_liquido": float(patrimonio) if patrimonio is not None else np.nan
        }
    except Exception:
        return {}