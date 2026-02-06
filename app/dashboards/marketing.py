# app/dashboards/marketing.py

import math
import streamlit as st
import pandas as pd
from app.dashboards.utils import (
    pct,
    explain_kpi,
    format_brl,
    metric_with_tooltip,
    cached_quality_tag,
)
from typing import Optional

def _safe_sum(df: pd.DataFrame, candidates) -> float:
    """Soma a primeira coluna existente na lista candidates; retorna 0.0 se nenhuma existir."""
    for c in candidates:
        if c in df.columns:
            try:
                return float(pd.to_numeric(df[c], errors="coerce").fillna(0).sum())
            except Exception:
                return 0.0
    return 0.0

def show_marketing(df: Optional[pd.DataFrame], modo: str = "Resumido"):
    st.subheader("📣 Marketing")

    if df is None:
        df = pd.DataFrame()

    # nomes possíveis de colunas (robusto para diferentes uploads)
    visitas = _safe_sum(df, ["visitas", "visits", "impressões", "impressões_visitas"])
    leads = _safe_sum(df, ["leads_gerados", "leads", "leads_total"])
    clientes = _safe_sum(df, ["clientes", "clientes_ativos", "clientes_conquistados"])
    investimento = _safe_sum(df, ["investimento", "invest", "custo_marketing"])
    receita = _safe_sum(df, ["receita", "receita_marketing", "receita_total"])

    # conversões (usar pct que retorna 0..100)
    conv_visita_lead = pct(leads, visitas)
    conv_lead_cliente = pct(clientes, leads)
    conv_total = pct(clientes, visitas)

    # CAC e ROI (tratamento defensivo)
    cac = None
    if clientes and clientes > 0:
        cac = investimento / clientes
    else:
        cac = math.nan

    roi_value = None
    if investimento and investimento != 0:
        roi_value = (receita - investimento) / investimento
    else:
        roi_value = math.nan
    roi_pct = roi_value * 100 if not (roi_value is None or math.isnan(roi_value)) else math.nan

    # Quality tags (usa thresholds automáticos quando disponíveis)
    cac_label, cac_tag, cac_color = cached_quality_tag(cac, kpi_name="cac")
    roi_label, roi_tag, roi_color = cached_quality_tag(roi_value, kpi_name="roi")

    # Exibição dos KPIs principais
    col1, col2, col3 = st.columns(3)
    with col1:
        explain_kpi(
            "Conversão Visitas → Leads",
            f"{conv_visita_lead:.1f}%" if not math.isnan(conv_visita_lead) else "—",
            percent=conv_visita_lead,
            base_label="Visitas",
            help_text="Percentual de visitas que foram convertidas em leads.",
        )
    with col2:
        explain_kpi(
            "Conversão Leads → Clientes",
            f"{conv_lead_cliente:.1f}%" if not math.isnan(conv_lead_cliente) else "—",
            percent=conv_lead_cliente,
            base_label="Leads",
            help_text="Percentual de leads que se tornaram clientes.",
        )
    with col3:
        explain_kpi(
            "Conversão Total (visita→cliente)",
            f"{conv_total:.1f}%" if not math.isnan(conv_total) else "—",
            percent=conv_total,
            base_label="Visitas",
            help_text="Percentual de visitas que resultaram em cliente.",
        )

    col4, col5 = st.columns(2)
    with col4:
        explain_kpi(
            "CAC (Custo por Aquisição)",
            format_brl(cac) if not (cac is None or math.isnan(cac)) else "—",
            help_text="Investimento / Clientes. Custo médio para conquistar um cliente.",
            color=cac_color
        )
    with col5:
        explain_kpi(
            "ROI",
            f"{roi_pct:.1f}%" if not (roi_pct is None or math.isnan(roi_pct)) else "—",
            percent=roi_pct,
            base_label="Investimento",
            help_text="(Receita − Investimento) / Investimento.",
            color=roi_color
        )

    # Indicadores auxiliares simples
    col6, col7 = st.columns(2)
    with col6:
        metric_with_tooltip(
            "Investimento total",
            format_brl(investimento) if investimento and not math.isnan(investimento) else "—",
            tooltip="Total investido em marketing no período."
        )
    with col7:
        metric_with_tooltip(
            "Receita atribuída",
            format_brl(receita) if receita and not math.isnan(receita) else "—",
            tooltip="Receita atribuída às ações de marketing no período."
        )

    # Detalhamento opcional
    if modo == "Detalhado":
        st.markdown("### 📊 Detalhamento de campanhas / linhas")
        if df.empty:
            st.info("Sem dados de marketing para o período selecionado.")
            return
        # mostra colunas selecionadas para clareza
        display_cols = [c for c in ["mes", "visitas", "leads_gerados", "leads", "clientes", "investimento", "receita"] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)