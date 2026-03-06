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

# utilitários defensivos para KPIs
def _to_num(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _safe_div(a, b):
    try:
        a = _to_num(a)
        b = _to_num(b)
        if a is None or b is None:
            return None
        if b == 0 or math.isinf(a) or math.isinf(b) or math.isnan(a) or math.isnan(b):
            return None
        return a / b
    except Exception:
        return None

def _compute_ebitda_from_dre_row(r):
    # EBITDA ≈ receita_bruta - cpv - csp - despesas_vendas - despesas_administrativas - outras_despesas
    try:
        rb = _to_num(r.get("receita_bruta") or r.get("receita") or 0) or 0
        cpv = _to_num(r.get("custo_produto_vendido") or 0) or 0
        csp = _to_num(r.get("custo_servico_prestado") or 0) or 0
        dv = _to_num(r.get("despesas_vendas") or 0) or 0
        da = _to_num(r.get("despesas_administrativas") or 0) or 0
        od = _to_num(r.get("outras_despesas") or 0) or 0
        return rb - cpv - csp - dv - da - od
    except Exception:
        return None

def _compute_cagr(series, periods_per_year=12):
    # series: pd.Series indexed by time-ordered values (numeric). returns CAGR decimal or None
    try:
        s = pd.to_numeric(series.dropna(), errors="coerce")
        if s.empty or len(s) < 2:
            return None
        first = float(s.iloc[0])
        last = float(s.iloc[-1])
        if first <= 0 or last <= 0:
            return None
        n_periods = len(s) - 1
        years = n_periods / periods_per_year
        if years <= 0:
            return None
        return (last / first) ** (1.0 / years) - 1.0
    except Exception:
        return None

def compute_kpis_from_dfs(df_fin: Optional[pd.DataFrame], df_cont: Optional[pd.DataFrame]):
    """
    Retorna dict com chaves por tenant e agregados:
    {
      "per_tenant": { tenant_id: {"ebitda":..., "margem_liquida":..., "roi":..., "roe":..., "cagr_receitas":..., "divida_ebitda":...}, ...},
      "aggregate": {"ebitda_total":..., "roi":..., ...}
    }
    """
    out = {"per_tenant": {}, "aggregate": {}}
    if df_fin is None:
        df_fin = pd.DataFrame()
    if df_cont is None:
        df_cont = pd.DataFrame()

    # normalizar tipos
    for col in ["ebitda", "lucro_liquido", "receita", "receita_bruta", "divida_liquida", "patrimonio_liquido"]:
        if col in df_fin.columns:
            df_fin[col] = pd.to_numeric(df_fin[col], errors="coerce")
        if col in df_cont.columns:
            df_cont[col] = pd.to_numeric(df_cont[col], errors="coerce")

    tenants = set()
    if "tenant_id" in df_fin.columns:
        tenants.update(df_fin["tenant_id"].dropna().unique().tolist())
    if "tenant_id" in df_cont.columns:
        tenants.update(df_cont["tenant_id"].dropna().unique().tolist())
    if not tenants:
        tenants = {None}

    # processar por tenant
    ebitda_sum = 0.0
    ebitda_count = 0
    roi_vals = []
    roe_vals = []
    cagr_vals = []
    div_ebitda_vals = []

    for tenant in tenants:
        tmask_fin = df_fin["tenant_id"] == tenant if "tenant_id" in df_fin.columns else pd.Series([False]*len(df_fin))
        tmask_cont = df_cont["tenant_id"] == tenant if "tenant_id" in df_cont.columns else pd.Series([False]*len(df_cont))

        df_t_fin = df_fin[tmask_fin].copy() if not df_fin.empty else pd.DataFrame()
        df_t_cont = df_cont[tmask_cont].copy() if not df_cont.empty else pd.DataFrame()

        # EBITDA: prefer coluna em indicadores_financeiros; fallback para DRE
        ebitda = None
        if "ebitda" in df_t_fin.columns and not df_t_fin["ebitda"].dropna().empty:
            ebitda = float(df_t_fin["ebitda"].dropna().astype(float).sum())  # soma do período
        else:
            # tentar calcular a partir de dre_financeiro (se estiver no mesmo df_fin ou em outro DF)
            if "receita_bruta" in df_t_fin.columns or "receita_bruta" in df_fin.columns:
                # tentar usar linhas correspondentes por mes
                try:
                    # se df_fin contém colunas DRE, calc por linha
                    if "receita_bruta" in df_t_fin.columns:
                        ebitda_series = df_t_fin.apply(_compute_ebitda_from_dre_row, axis=1)
                        if not ebitda_series.dropna().empty:
                            ebitda = float(ebitda_series.sum())
                except Exception:
                    ebitda = None

        # Margem líquida: média do período = mean(lucro_liquido / receita)
        margem_liq = None
        if "lucro_liquido" in df_t_fin.columns and ("receita" in df_t_fin.columns or "receita_bruta" in df_t_fin.columns):
            rev_col = "receita" if "receita" in df_t_fin.columns else "receita_bruta"
            ratios = []
            for _, r in df_t_fin.iterrows():
                lucro = _to_num(r.get("lucro_liquido"))
                rev = _to_num(r.get(rev_col))
                val = _safe_div(lucro, rev)
                if val is not None:
                    ratios.append(val)
            margem_liq = float(pd.Series(ratios).mean()) if ratios else None

        # ROE: lucro_liquido / patrimonio_liquido (usar último patrimônio)
        roe = None
        last_pl = None
        if not df_t_cont.empty and "patrimonio_liquido" in df_t_cont.columns:
            try:
                last_pl = pd.to_numeric(df_t_cont["patrimonio_liquido"], errors="coerce").dropna()
                if not last_pl.empty:
                    last_pl = float(last_pl.iloc[-1])
            except Exception:
                last_pl = None
        # lucro líquido total do período (soma)
        lucro_total = None
        if "lucro_liquido" in df_t_fin.columns and not df_t_fin["lucro_liquido"].dropna().empty:
            lucro_total = float(df_t_fin["lucro_liquido"].dropna().astype(float).sum())
        if lucro_total is not None and last_pl is not None:
            roe = _safe_div(lucro_total, last_pl)

        # ROI: se existir coluna 'investimento' usar lucro_total / investimento_total; fallback lucro_total / patrimonio_liquido
        roi = None
        invest_total = None
        if "investimento" in df_t_fin.columns and not df_t_fin["investimento"].dropna().empty:
            invest_total = float(df_t_fin["investimento"].dropna().astype(float).sum())
        if lucro_total is not None and invest_total is not None:
            roi = _safe_div(lucro_total, invest_total)
        elif lucro_total is not None and last_pl is not None:
            roi = _safe_div(lucro_total, last_pl)

        # CAGR receitas: usar série de receita (ordenada por mes)
        cagr = None
        if "receita" in df_t_fin.columns or "receita_bruta" in df_t_fin.columns:
            rev_col = "receita" if "receita" in df_t_fin.columns else "receita_bruta"
            s = df_t_fin.sort_values("mes")[rev_col] if "mes" in df_t_fin.columns else df_t_fin[rev_col]
            cagr = _compute_cagr(s, periods_per_year=12)

        # Dívida / EBITDA: usar divida_liquida (última) / ebitda (soma ou último)
        divida_ebitda = None
        last_div = None
        if not df_t_cont.empty and "divida_liquida" in df_t_cont.columns:
            try:
                last_div = pd.to_numeric(df_t_cont["divida_liquida"], errors="coerce").dropna()
                if not last_div.empty:
                    last_div = float(last_div.iloc[-1])
            except Exception:
                last_div = None
        # ebitda for ratio: prefer sum over period, else last
        ebitda_for_ratio = ebitda
        if ebitda_for_ratio is None and "ebitda" in df_t_fin.columns and not df_t_fin["ebitda"].dropna().empty:
            ebitda_for_ratio = float(df_t_fin["ebitda"].dropna().astype(float).iloc[-1])
        if last_div is not None and ebitda_for_ratio is not None:
            divida_ebitda = _safe_div(last_div, ebitda_for_ratio)

        # store
        out["per_tenant"][tenant] = {
            "ebitda": ebitda,
            "margem_liquida": margem_liq,
            "roi": roi,
            "roe": roe,
            "cagr_receitas": cagr,
            "divida_ebitda": divida_ebitda,
            "lucro_total": lucro_total,
            "patrimonio_liquido": last_pl,
            "valor_mercado": None
        }

        # aggregate trackers
        if ebitda is not None:
            ebitda_sum += ebitda
            ebitda_count += 1
        if roi is not None:
            roi_vals.append(roi)
        if roe is not None:
            roe_vals.append(roe)
        if cagr is not None:
            cagr_vals.append(cagr)
        if divida_ebitda is not None:
            div_ebitda_vals.append(divida_ebitda)

    # aggregates
    out["aggregate"]["ebitda_total"] = ebitda_sum if ebitda_count > 0 else None
    out["aggregate"]["roi_mean"] = float(pd.Series(roi_vals).mean()) if roi_vals else None
    out["aggregate"]["roe_mean"] = float(pd.Series(roe_vals).mean()) if roe_vals else None
    out["aggregate"]["cagr_mean"] = float(pd.Series(cagr_vals).mean()) if cagr_vals else None
    out["aggregate"]["divida_ebitda_mean"] = float(pd.Series(div_ebitda_vals).mean()) if div_ebitda_vals else None

    return out

def show_estrategicos(df_fin: Optional[pd.DataFrame], df_cont: Optional[pd.DataFrame], modo: str = "Resumido", derived_metrics: Optional[Dict[str, Any]] = None):
    st.subheader("📊 Indicadores Estratégicos")

    dm = derived_metrics or {}

    kpis = compute_kpis_from_dfs(df_fin, df_cont)
    # preencher dm com fallbacks do compute_kpis_from_dfs.aggregate
    dm.setdefault("ebitda", dm.get("ebitda") or kpis["aggregate"].get("ebitda_total"))
    dm.setdefault("roi", dm.get("roi") or kpis["aggregate"].get("roi_mean"))
    dm.setdefault("roe", dm.get("roe") or kpis["aggregate"].get("roe_mean"))
    dm.setdefault("cagr_receitas", dm.get("cagr_receitas") or kpis["aggregate"].get("cagr_mean"))
    dm.setdefault("margem_liquida", dm.get("margem_liquida") or kpis["aggregate"].get("margem_mean") if kpis["aggregate"].get("margem_mean") else dm.get("margem_liquida"))
    dm.setdefault("divida_ebitda", dm.get("divida_ebitda") or kpis["aggregate"].get("divida_ebitda_mean"))

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
