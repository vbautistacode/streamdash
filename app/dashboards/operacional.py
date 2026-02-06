# app/dashboards/operacional.py

import streamlit as st
import pandas as pd
from app.dashboards.utils import cached_quality_tag, format_brl, metric_with_tooltip
from app.dashboards.utils import pct as _pct  # se precisar calcular percentuais locais

def _safe_mean(df: pd.DataFrame, col: str):
    if df is None or df.empty or col not in df.columns:
        return None
    try:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        return float(vals.mean()) if not vals.empty else None
    except Exception:
        return None

def show_ops(df: pd.DataFrame, modo: str = "Resumido"):
    st.subheader("⚙️ Indicadores Operacionais")

    produtividade = _safe_mean(df, "produtividade")
    eficiencia = _safe_mean(df, "eficiencia")
    producao = _safe_mean(df, "producao")
    custo_unidade = _safe_mean(df, "custo_unidade")

    # quality tags (usa cached wrapper que aceita kpi_name para thresholds automáticos)
    prod_label, prod_tag, prod_color = cached_quality_tag(produtividade, kpi_name="produtividade")
    ef_label, ef_tag, ef_color = cached_quality_tag(eficiencia, kpi_name="produtividade")  # compartilhar thresholds se desejar outro kpi, ajuste kpi_name
    prod_display = f"{produtividade:.2f}" if produtividade is not None else "—"
    ef_display = f"{eficiencia:.2f}" if eficiencia is not None else "—"

    col1, col2 = st.columns(2)
    with col1:
        metric_with_tooltip(
            "Produtividade (média)",
            prod_display,
            "Output por unidade de insumo (média do período).",
            tag_key=prod_tag,
            formatter=None
        )
    with col2:
        metric_with_tooltip(
            "Eficiência (média)",
            ef_display,
            "Relação entre output ideal e realizado (média do período).",
            tag_key=ef_tag,
            formatter=None
        )

    # Exibir produção e custo por unidade como indicadores auxiliares
    col3, col4 = st.columns(2)
    with col3:
        metric_with_tooltip(
            "Produção (média)",
            f"{producao:.2f}" if producao is not None else "—",
            "Unidades produzidas (média do período).",
            formatter=None
        )
    with col4:
        metric_with_tooltip(
            "Custo por unidade",
            format_brl(custo_unidade) if custo_unidade is not None else "—",
            "Custo médio por unidade produzida.",
            formatter=None
        )

    if modo == "Detalhado":
        st.markdown("### 📊 Detalhamento")
        if df is None or df.empty:
            st.info("Sem dados operacionais para o período selecionado.")
            return

        st.dataframe(df, use_container_width=True)
        if {"mes", "produtividade", "eficiencia"}.issubset(df.columns):
            try:
                chart_df = df.sort_values("mes").set_index("mes")[["produtividade", "eficiencia"]]
                # garante colunas numéricas para o chart
                chart_df = chart_df.apply(pd.to_numeric, errors="coerce")
                st.line_chart(chart_df)
            except Exception:
                st.warning("Não foi possível gerar o gráfico de séries (verifique os dados de 'mes').")