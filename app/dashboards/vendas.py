# app/dashboards/vendas.py
import streamlit as st
import pandas as pd
import numpy as np
from typing import Optional, Tuple

from app.dashboards.utils import (
    pct,
    explain_kpi,
    format_brl,
    metric_with_tooltip,
    cached_quality_tag
)

# -----------------------------
# Utilitários locais
# -----------------------------
def _safe_mean(df: Optional[pd.DataFrame], col: str) -> Optional[float]:
    if df is None or df.empty or col not in df.columns:
        return None
    try:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        return float(vals.mean()) if not vals.empty else None
    except Exception:
        return None

def _safe_sum(df: Optional[pd.DataFrame], col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    try:
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    except Exception:
        return 0.0

# -----------------------------
# Fallbacks e cálculos
# -----------------------------
def calc_ticket_medio_from_raw(
    df_vendas: Optional[pd.DataFrame],
    receita_col: str = "receita",
    transacoes_col: str = "volume_vendas",
    finance_df: Optional[pd.DataFrame] = None,
    mkt_df: Optional[pd.DataFrame] = None
) -> Optional[float]:
    """
    Estima ticket médio:
    - Se houver coluna ticket_medio retorna a média;
    - Senão tenta (receita disponível em vendas + marketing + entradas do financeiro) / volume_vendas.
    """
    # já existe ticket_medio
    mean_ticket = _safe_mean(df_vendas, "ticket_medio")
    if mean_ticket is not None:
        return mean_ticket

    # soma receitas candidatas
    total_revenue = 0.0
    # receita dentro do próprio df_vendas (campo comum 'receita')
    total_revenue += _safe_sum(df_vendas, receita_col) if df_vendas is not None else 0.0
    # receitas vindas de marketing (opcional)
    total_revenue += _safe_sum(mkt_df, "receita") if mkt_df is not None else 0.0
    # entradas financeiras (fallback)
    total_revenue += _safe_sum(finance_df, "entradas") if finance_df is not None else 0.0

    # transações / volume
    total_volume = _safe_sum(df_vendas, transacoes_col)

    if total_volume and total_volume != 0:
        return float(total_revenue) / float(total_volume)
    return None

def calc_conversion_rates(
    df_vendas: Optional[pd.DataFrame] = None,
    mkt_df: Optional[pd.DataFrame] = None,
    clientes_df: Optional[pd.DataFrame] = None
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Retorna (conv_visitas_leads, conv_leads_clientes, conv_total)
    - conv_visitas_leads = leads / visitas
    - conv_leads_clientes = clientes / leads
    - conv_total = clientes / visitas
    Usa colunas: visitas, leads_gerados, clientes_ativos quando disponíveis
    """
    visitas = _safe_sum(mkt_df, "visitas") if mkt_df is not None else 0.0
    leads = _safe_sum(mkt_df, "leads_gerados") if mkt_df is not None else _safe_sum(df_vendas, "leads_gerados")
    clientes = _safe_sum(clientes_df, "clientes_ativos") if clientes_df is not None else _safe_sum(df_vendas, "clientes_ativos")

    conv_vis_leads = (leads / visitas) if visitas and visitas != 0 else None
    conv_leads_cli = (clientes / leads) if leads and leads != 0 else None
    conv_total = (clientes / visitas) if visitas and visitas != 0 else None
    return conv_vis_leads, conv_leads_cli, conv_total

def calc_churn_from_series(clientes_df: Optional[pd.DataFrame]) -> Optional[float]:
    """
    Estima churn a partir da série clientes_ativos ordenada por mes:
    churn = (start - end) / start
    """
    if clientes_df is None or clientes_df.empty or "clientes_ativos" not in clientes_df.columns:
        return None
    try:
        s = pd.to_numeric(clientes_df["clientes_ativos"], errors="coerce").dropna()
        if len(s) < 2:
            return None
        start = s.iloc[0]
        end = s.iloc[-1]
        if start == 0 or pd.isna(start):
            return None
        churn = (start - end) / start
        return float(churn) if churn >= 0 else None
    except Exception:
        return None

def calc_ltv(df_vendas: Optional[pd.DataFrame], clientes_df: Optional[pd.DataFrame] = None) -> Optional[float]:
    """
    Tenta obter LTV:
    - se coluna ltv presente usa média;
    - senão fallback receita_total / clientes_ativos (onde receita_total pode estar em vendas)
    """
    mean_ltv = _safe_mean(df_vendas, "ltv")
    if mean_ltv is not None:
        return mean_ltv

    receita_total = _safe_sum(df_vendas, "receita")
    clientes = _safe_sum(clientes_df, "clientes_ativos") if clientes_df is not None else _safe_sum(df_vendas, "clientes_ativos")
    if clientes and clientes != 0:
        return float(receita_total) / float(clientes)
    return None

# -----------------------------
# Main: show_sales
# -----------------------------
def show_sales(
    df: Optional[pd.DataFrame],
    modo: str = "Resumido",
    finance_df: Optional[pd.DataFrame] = None,
    mkt_df: Optional[pd.DataFrame] = None,
    clientes_df: Optional[pd.DataFrame] = None
):
    """
    Exibe indicadores de vendas.
    Parâmetros adicionais opcionais permitem passar DFs auxiliares para cálculos quando necessário.
    """
    st.subheader("🛒 Indicadores de Vendas")

    if df is None:
        df = pd.DataFrame()

    # valores básicos
    ticket_medio = _safe_mean(df, "ticket_medio") or calc_ticket_medio_from_raw(df, receita_col="receita", transacoes_col="volume_vendas", finance_df=finance_df, mkt_df=mkt_df)
    taxa_conversao = _safe_mean(df, "taxa_conversao")
    if taxa_conversao is None:
        _, _, taxa_conversao = calc_conversion_rates(df_vendas=df, mkt_df=mkt_df, clientes_df=clientes_df)

    volume_vendas = _safe_sum(df, "volume_vendas")
    churn_rate = _safe_mean(df, "churn_rate") or calc_churn_from_series(clientes_df)
    ltv_medio = _safe_mean(df, "ltv") or calc_ltv(df, clientes_df=clientes_df)

    # quality tags (cached_quality_tag returns (label, tag_key, color) in this codebase)
    _, vol_tag, vol_color = cached_quality_tag(volume_vendas, kpi_name="volume_vendas")
    _, conv_tag, conv_color = cached_quality_tag(taxa_conversao, kpi_name="taxa_conversao")
    _, churn_tag, churn_color = cached_quality_tag(churn_rate, kpi_name="churn_rate")

    # render métricas
    col1, col2, col3 = st.columns(3)
    with col1:
        metric_with_tooltip(
            "Ticket Médio",
            format_brl(ticket_medio) if ticket_medio is not None else "—",
            "Valor médio por venda.",
            tag_key=None
        )
    with col2:
        metric_with_tooltip(
            "Taxa de Conversão",
            f"{taxa_conversao:.2%}" if taxa_conversao is not None else "—",
            "Percentual de leads/visitas que converteram.",
            tag_key=conv_tag
        )
    with col3:
        metric_with_tooltip(
            "Volume de Vendas",
            f"{int(volume_vendas):,}" if volume_vendas is not None and volume_vendas != 0 else "—",
            "Unidades / transações no período.",
            tag_key=vol_tag
        )

    col4, col5 = st.columns(2)
    with col4:
        metric_with_tooltip(
            "Churn Rate",
            f"{churn_rate:.2%}" if churn_rate is not None else "—",
            "Percentual de clientes que cancelaram.",
            tag_key=churn_tag
        )
    with col5:
        metric_with_tooltip(
            "LTV Médio",
            format_brl(ltv_medio) if ltv_medio is not None else "—",
            "Valor vitalício médio do cliente.",
            tag_key=None
        )

    # detalhado
    if modo == "Detalhado":
        st.markdown("### 📊 Detalhamento de vendas")
        if df.empty:
            st.info("Sem dados de vendas para o período selecionado.")
            return
        display_cols = [c for c in ["mes", "ticket_medio", "taxa_conversao", "volume_vendas", "churn_rate", "ltv"] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)