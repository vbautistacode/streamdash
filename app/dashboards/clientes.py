# app/dashboards/clientes.py

import math
import streamlit as st
import pandas as pd
from typing import Optional

from app.dashboards.utils import (
    pct,
    format_brl,
    metric_with_tooltip,
    cached_quality_tag,
)

def _safe_sum(df: Optional[pd.DataFrame], col: str) -> int:
    if df is None or df.empty or col not in df.columns:
        return 0
    try:
        return int(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    except Exception:
        return 0

def _safe_mean(df: Optional[pd.DataFrame], col: str) -> Optional[float]:
    if df is None or df.empty or col not in df.columns:
        return None
    try:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        return float(vals.mean()) if not vals.empty else None
    except Exception:
        return None

def show_clients(df: Optional[pd.DataFrame], modo: str = "Resumido"):
    """
    Exibe indicadores de clientes.
    - df: DataFrame filtrado (mês único ou acumulado) contendo colunas como clientes_ativos, churn_rate, taxa_retencao, nps.
    - modo: "Resumido" ou "Detalhado".
    """
    st.subheader("👥 Indicadores de Clientes")

    if df is None:
        df = pd.DataFrame()

    # Principais métricas
    n_clientes = _safe_sum(df, "clientes_ativos")
    churn = _safe_mean(df, "churn_rate")
    taxa_retencao = _safe_mean(df, "taxa_retencao")
    nps = _safe_mean(df, "nps")

    # Crescimento de clientes no período (quando há séries)
    crescimento_pct = None
    if df is not None and not df.empty and "mes" in df.columns and "clientes_ativos" in df.columns and df["mes"].nunique() >= 2:
        try:
            df_ord = df.sort_values("mes")
            inicio = pd.to_numeric(df_ord["clientes_ativos"].iloc[0], errors="coerce")
            fim = pd.to_numeric(df_ord["clientes_ativos"].iloc[-1], errors="coerce")
            if pd.notna(inicio) and inicio != 0:
                crescimento_pct = pct(fim - inicio, inicio)
            else:
                crescimento_pct = None
        except Exception:
            crescimento_pct = None

    # Quality tag para churn (menor é melhor)
    churn_label, churn_tag, churn_color = cached_quality_tag(churn, kpi_name="churn_rate")

    # Layout principal
    col1, col2 = st.columns(2)
    with col1:
        metric_with_tooltip(
            "Clientes Ativos",
            f"{n_clientes:,}" if n_clientes else "—",
            tooltip="Total de clientes com relacionamento ativo no período.",
            tag_key=None
        )
        if crescimento_pct is not None:
            st.caption(f"Crescimento no período: {crescimento_pct:.1f}%")

    with col2:
        metric_with_tooltip(
            "Churn Rate",
            f"{churn:.2%}" if churn is not None else "—",
            tooltip="Percentual de clientes que cancelaram no período.",
            tag_key=churn_tag
        )

    # Indicadores complementares
    col3, col4 = st.columns(2)
    with col3:
        metric_with_tooltip(
            "Taxa de Retenção",
            f"{taxa_retencao:.1%}" if taxa_retencao is not None else "—",
            tooltip="Proporção de clientes retidos no período.",
            tag_key=None
        )
    with col4:
        metric_with_tooltip(
            "NPS (média)",
            f"{nps:.1f}" if nps is not None else "—",
            tooltip="Net Promoter Score médio no período.",
            tag_key=None
        )

    # Modo detalhado: tabela e séries
    if modo == "Detalhado":
        st.markdown("### 📊 Detalhamento")
        if df is None or df.empty:
            st.info("Sem dados de clientes para o período selecionado.")
            return

        # Mostrar tabela com colunas relevantes quando disponíveis
        display_cols = [c for c in ["mes", "clientes_ativos", "churn_rate", "taxa_retencao", "nps"] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)

        # Gráfico de séries (clientes ativos e churn)
        if {"mes", "clientes_ativos"}.issubset(df.columns):
            try:
                chart_df = df.sort_values("mes").set_index("mes")
                plot_cols = []
                if "clientes_ativos" in chart_df.columns:
                    plot_cols.append("clientes_ativos")
                if "churn_rate" in chart_df.columns:
                    # churn_rate em % para visualização (multiplicar por 100)
                    chart_df["churn_pct"] = pd.to_numeric(chart_df["churn_rate"], errors="coerce") * 100.0
                    plot_cols.append("churn_pct")
                if plot_cols:
                    st.line_chart(chart_df[plot_cols])
            except Exception:
                st.warning("Não foi possível gerar o gráfico de séries (verifique os dados de 'mes').")