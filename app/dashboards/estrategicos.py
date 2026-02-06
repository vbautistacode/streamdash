# app/dashboards/estrategicos.py
import math
import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any

from app.dashboards.utils import format_brl, metric_with_tooltip, cached_quality_tag

# import ML inferência (defensivo)
try:
    from ml.predict import detect_anomalies, forecast_trend, recommend_actions
except Exception:
    detect_anomalies = None
    forecast_trend = None
    recommend_actions = None

def show_estrategicos(df_fin: Optional[pd.DataFrame], df_cont: Optional[pd.DataFrame], modo: str = "Resumido", derived_metrics: Optional[Dict[str, Any]] = None):
    st.subheader("📊 Indicadores Estratégicos")

    dm = derived_metrics or {}

    def _safe_mean(df, col):
        try:
            if df is None or df.empty or col not in df.columns:
                return None
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            return float(vals.mean()) if not vals.empty else None
        except Exception:
            return None

    def _safe_sum(df, col):
        try:
            if df is None or df.empty or col not in df.columns:
                return None
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            return float(vals.sum()) if not vals.empty else None
        except Exception:
            return None

    def _safe_last(df, col):
        try:
            if df is None or df.empty or col not in df.columns:
                return None
            d = df.copy()
            if "mes" in d.columns:
                try:
                    d["__mes_dt"] = pd.to_datetime(d["mes"], errors="coerce")
                    d = d.sort_values("__mes_dt")
                except Exception:
                    d = d.sort_values("mes")
            return d.iloc[-1].get(col)
        except Exception:
            return None

    def _fmt_pct(x):
        try:
            if x is None:
                return "—"
            xf = float(x)
            if math.isnan(xf):
                return "—"
            return f"{xf:.2%}"
        except Exception:
            return "—"

    def _fmt_num(x):
        try:
            if x is None:
                return "—"
            return format_brl(x)
        except Exception:
            return "—"

    ebitda_total = dm.get("ebitda") or dm.get("ebitda_total") or _safe_sum(df_fin, "ebitda")
    margem_liquida = dm.get("margem_liquida") or _safe_mean(df_fin, "margem_liquida")
    roi = dm.get("roi") or _safe_mean(df_fin, "roi")
    cagr_receitas = dm.get("cagr_receitas") or dm.get("cagr") or _safe_mean(df_fin, "cagr_receitas")

    roe = dm.get("roe") or _safe_mean(df_fin, "roe")
    divida_ebitda = dm.get("divida_ebitda") or _safe_mean(df_fin, "divida_ebitda")

    patrimonio_liquido = dm.get("patrimonio_liquido") or _safe_last(df_cont, "patrimonio_liquido")
    valor_mercado = dm.get("valor_mercado") or _safe_last(df_cont, "valor_mercado")
    valor_firma = dm.get("valor_firma") or _safe_last(df_cont, "valor_firma")
    tipo_empresa = dm.get("tipo_empresa") or _safe_last(df_cont, "tipo_empresa")

    # Inferência ML defensiva
    anomalies_df = None
    forecasts = {}
    recs = []
    try:
        if detect_anomalies is not None:
            anomalies_df = detect_anomalies(df_fin if df_fin is not None else pd.DataFrame())
    except Exception:
        anomalies_df = None

    for metric in ("receita", "ebitda", "roi"):
        try:
            if forecast_trend is not None:
                f = forecast_trend(df_fin if df_fin is not None else pd.DataFrame(), metric, periods=3)
                if f is not None:
                    forecasts[metric] = f
        except Exception:
            forecasts[metric] = None

    try:
        if recommend_actions is not None:
            recs = recommend_actions(df_fin if df_fin is not None else pd.DataFrame(), anomalies_df, forecasts)
    except Exception:
        recs = []

    # Resumido: ROI, Margem Líquida, EBITDA, CAGR
    if modo == "Resumido":
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_with_tooltip("ROI (médio)", _fmt_pct(roi), tooltip="Retorno médio sobre investimento no período.")
        with c2:
            metric_with_tooltip("Margem Líquida", _fmt_pct(margem_liquida), tooltip="Lucro líquido / Receita.")
        with c3:
            metric_with_tooltip("EBITDA (total)", _fmt_num(ebitda_total), tooltip="Proxy de geração de caixa operacional.")
        with c4:
            metric_with_tooltip("CAGR Receitas", _fmt_pct(cagr_receitas), tooltip="Crescimento anual composto das receitas.")
        return

    # Detalhado: todos e evolução
    st.markdown("#### Indicadores")
    cols = st.columns(3)
    cols[0].write("**ROI (médio)**"); cols[0].write(_fmt_pct(roi))
    cols[1].write("**Margem Líquida**"); cols[1].write(_fmt_pct(margem_liquida))
    cols[2].write("**EBITDA (total)**"); cols[2].write(_fmt_num(ebitda_total))

    cols2 = st.columns(3)
    cols2[0].write("**CAGR Receitas**"); cols2[0].write(_fmt_pct(cagr_receitas))
    cols2[1].write("**ROE**"); cols2[1].write(_fmt_pct(roe))
    cols2[2].write("**Dívida / EBITDA**"); cols2[2].write(f"{divida_ebitda:.2f}" if divida_ebitda is not None else "—")

    st.divider()

    # Evolução temporal
    def _prepare_time_series(df, cols):
        if df is None or df.empty:
            return None
        d = df.copy()
        if "mes_norm" in d.columns and d["mes_norm"].notna().any():
            d = d.dropna(subset=cols + ["mes_norm"])
            try:
                d = d.set_index(pd.to_datetime(d["mes_norm"].astype(str)))
            except Exception:
                d.index = d["mes_norm"].astype(str)
        elif "mes" in d.columns:
            d = d.dropna(subset=cols + ["mes"])
            try:
                d = d.set_index(pd.to_datetime(d["mes"].astype(str)))
            except Exception:
                d.index = d["mes"].astype(str)
        else:
            return None
        for c in cols:
            if c in d.columns:
                d[c] = pd.to_numeric(d[c], errors="coerce")
        return d[cols].dropna(how="all")

    ts_cols = [c for c in ["roi", "margem_liquida", "ebitda", "cagr_receitas"] if df_fin is not None and c in df_fin.columns]
    ts_df = _prepare_time_series(df_fin, ts_cols) if ts_cols else None
    if ts_df is not None and not ts_df.empty:
        st.markdown("#### Evolução")
        try:
            st.line_chart(ts_df)
        except Exception:
            st.warning("Não foi possível gerar os gráficos de evolução.")

    # Recomendações automáticas
    if recs:
        st.markdown("#### Recomendações automáticas")
        for i, r in enumerate(recs):
            st.markdown(f"**{r.get('title','Recomendação')}**")
            st.write(r.get("reason", "—"))
            st.caption(f"Impacto estimado: {r.get('impact_estimate','—')}")
            # mostrar drivers SHAP se existirem
            drivers = r.get("drivers")
            if drivers:
                st.markdown("**Drivers (explicabilidade)**")
                for d in drivers:
                    # d: {"index": idx, "top": [{"feature":..., "value":..., "contribution":...}, ...]}
                    st.write(f"- Linha: {d.get('index')}")
                    for feat in d.get("top", []):
                        feat_name = feat.get("feature")
                        feat_val = feat.get("value")
                        contrib = feat.get("contribution")
                        # formatação simples
                        st.write(f"  - **{feat_name}** = {feat_val:.2f}  → contribuição: {contrib:.3f}")
            # ação rápida: marcar investigado
            key = f"anomaly_action_{i}"
            if st.button("Marcar como investigado", key=key):
                if "anomaly_actions" not in st.session_state:
                    st.session_state["anomaly_actions"] = []
                st.session_state["anomaly_actions"].append({
                    "title": r.get("title"),
                    "reason": r.get("reason"),
                    "impact": r.get("impact_estimate"),
                    "drivers": r.get("drivers"),
                    "created_at": pd.Timestamp.now().isoformat()
                })
                st.success("Ação registrada localmente")
