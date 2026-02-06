# ml/predict.py
import os
import joblib
import numpy as np
import pandas as pd
from typing import List, Dict, Optional

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "isolation_forest.joblib")

def _load_model():
    if os.path.exists(MODEL_PATH):
        try:
            return joblib.load(MODEL_PATH)
        except Exception:
            return None
    return None

# tentativa de importar shap (opcional)
try:
    import shap
    _HAS_SHAP = True
except Exception:
    shap = None
    _HAS_SHAP = False

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    model = _load_model()
    for c in ["receita", "ebitda", "margem_liquida", "roi"]:
        if c not in df.columns:
            df[c] = 0.0
    if model is None:
        df["anomaly_score"] = 0.0
        df["is_anomaly"] = False
        return df

    X = df[["receita", "ebitda", "margem_liquida", "roi"]].apply(pd.to_numeric, errors="coerce").fillna(0).values
    try:
        # pipeline: scaler + iforest
        scores = model.decision_function(X)
        preds = model.predict(X)
        df["anomaly_score"] = scores
        df["is_anomaly"] = preds == -1
    except Exception:
        df["anomaly_score"] = 0.0
        df["is_anomaly"] = False
    return df

def _explain_with_shap(pipeline, df: pd.DataFrame, top_k: int = 3) -> Dict:
    """
    Retorna dict {index: [(feature, value, contribution), ...]} com top_k drivers por linha.
    Funciona apenas se shap estiver instalado e o pipeline for compatível.
    """
    explanations = {}
    if not _HAS_SHAP or pipeline is None:
        return explanations

    try:
        # extrair steps
        if hasattr(pipeline, "named_steps"):
            scaler = pipeline.named_steps.get("scaler", None)
            model = pipeline.named_steps.get("iforest", pipeline)
        else:
            scaler = None
            model = pipeline

        # preparar X
        X_df = df[["receita", "ebitda", "margem_liquida", "roi"]].apply(pd.to_numeric, errors="coerce").fillna(0)
        X = X_df.values

        # transformar se houver scaler
        if scaler is not None:
            try:
                X_trans = scaler.transform(X)
            except Exception:
                X_trans = X
        else:
            X_trans = X

        # tentar TreeExplainer (mais rápido para modelos de árvore)
        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_trans)
        except Exception:
            # fallback para Explainer genérico
            explainer = shap.Explainer(model, X_trans)
            shap_values = explainer(X_trans).values

        # shap_values shape: (n_samples, n_features) ou lista (para multiclass)
        if isinstance(shap_values, list):
            # pegar a primeira saída se for lista
            shap_arr = np.array(shap_values[0])
        else:
            shap_arr = np.array(shap_values)

        feature_names = list(X_df.columns)
        for i, idx in enumerate(df.index):
            row_shap = shap_arr[i]
            # pares (feature, value, contribution)
            feats = []
            for j, fname in enumerate(feature_names):
                feats.append((fname, float(X_df.iloc[i, j]), float(row_shap[j])))
            # ordenar por contribuição absoluta
            feats_sorted = sorted(feats, key=lambda x: abs(x[2]), reverse=True)[:top_k]
            explanations[idx] = feats_sorted
    except Exception:
        # se qualquer erro, retornar vazio (defensivo)
        return {}
    return explanations

def forecast_trend(df: pd.DataFrame, metric: str, periods: int = 3) -> Optional[pd.Series]:
    if df is None or df.empty or metric not in df.columns:
        return None
    d = df.copy()
    if "mes_norm" in d.columns and d["mes_norm"].notna().any():
        d["__t"] = pd.to_datetime(d["mes_norm"], errors="coerce")
    elif "mes_dt" in d.columns:
        d["__t"] = pd.to_datetime(d["mes_dt"], errors="coerce")
    elif "mes" in d.columns:
        d["__t"] = pd.to_datetime(d["mes"].astype(str), errors="coerce")
    else:
        d["__t"] = pd.RangeIndex(len(d))
    d = d.dropna(subset=["__t"])
    if d.empty:
        return None
    d = d.sort_values("__t")
    x = (d["__t"] - d["__t"].min()).dt.days.astype(float).values.reshape(-1, 1)
    y = pd.to_numeric(d[metric], errors="coerce").fillna(method="ffill").fillna(0).values
    if len(x) < 2:
        return None
    try:
        Xmat = np.hstack([np.ones_like(x), x])
        beta, *_ = np.linalg.lstsq(Xmat, y, rcond=None)
        last_t = d["__t"].max()
        future = []
        for i in range(1, periods + 1):
            ft = last_t + pd.DateOffset(months=i)
            days = (ft - d["__t"].min()).days
            x_new = np.array([1.0, float(days)])
            y_pred = float(x_new.dot(beta))
            future.append((ft.strftime("%Y-%m"), y_pred))
        return pd.Series({k: v for k, v in future})
    except Exception:
        return None

def _safe_div(num, den):
    try:
        if num is None or den is None:
            return None
        den_f = float(den)
        if den_f == 0:
            return None
        return float(num) / den_f
    except Exception:
        return None

def recommend_actions(df: pd.DataFrame, anomalies_df: pd.DataFrame, forecasts: Dict[str, pd.Series]) -> List[Dict]:
    recs = []
    model = _load_model()

    # preparar explicações SHAP para linhas anômalas (se possível)
    shap_explanations = {}
    try:
        if _HAS_SHAP and model is not None and anomalies_df is not None and "is_anomaly" in anomalies_df.columns:
            anom_rows = anomalies_df[anomalies_df["is_anomaly"]]
            if not anom_rows.empty:
                shap_explanations = _explain_with_shap(model, anom_rows, top_k=3)
    except Exception:
        shap_explanations = {}

    if anomalies_df is not None and "is_anomaly" in anomalies_df.columns:
        recent_anoms = anomalies_df[anomalies_df["is_anomaly"]].sort_values("mes" if "mes" in anomalies_df.columns else "mes_norm", ascending=False)
        if not recent_anoms.empty:
            cols = []
            if recent_anoms["receita"].notna().any():
                cols.append("receita")
            if recent_anoms["ebitda"].notna().any():
                cols.append("ebitda")
            # coletar drivers agregados (top features across anomalous rows)
            drivers = []
            for idx in recent_anoms.index:
                if idx in shap_explanations:
                    drivers.append({
                        "index": idx,
                        "top": [
                            {"feature": f, "value": v, "contribution": c}
                            for (f, v, c) in shap_explanations[idx]
                        ]
                    })
            recs.append({
                "title": "Investigar anomalias recentes",
                "reason": f"Foram detectadas anomalias nas colunas: {', '.join(cols)}. Verificar causas (promoções, erros de integração, lançamentos).",
                "impact_estimate": "Alto" if "ebitda" in cols else "Médio",
                "drivers": drivers if drivers else None
            })

    for metric, series in (forecasts or {}).items():
        if series is None or series.empty:
            continue
        try:
            last_forecast = float(series.iloc[-1])
            hist_mean = float(pd.to_numeric(df[metric], errors="coerce").mean())
            if last_forecast < hist_mean * 0.98:
                recs.append({
                    "title": f"Rever estratégia para {metric}",
                    "reason": f"Forecast indica queda em {metric} (previsto {last_forecast:.0f} vs média histórica {hist_mean:.0f}). Considere ações de preço ou marketing.",
                    "impact_estimate": "Médio",
                    "drivers": None
                })
        except Exception:
            continue

    if not recs:
        recs.append({
            "title": "Revisão periódica",
            "reason": "Nenhuma anomalia ou tendência negativa detectada; manter monitoramento mensal.",
            "impact_estimate": "Baixo",
            "drivers": None
        })
    return recs