#period_utils.py

import pandas as pd
from typing import Optional

def normalize_mes_column(df: pd.DataFrame, col: str = "mes") -> pd.DataFrame:
    if col in df.columns and not df.empty:
        df = df.copy()
        df["mes_norm"] = pd.to_datetime(df[col].astype(str), errors="coerce").dt.to_period("M").astype(str)
        mask = df["mes_norm"].isna()
        if mask.any():
            df.loc[mask, "mes_norm"] = df.loc[mask, col].astype(str).str.strip().str.slice(0,7)
        return df
    df = df.copy()
    df["mes_norm"] = None
    return df

def prepare_period_view(df: pd.DataFrame, periodo: Optional[str]) -> dict:
    """
    Retorna dict com chaves:
      - 'view': "mensal" | "acumulado" | "mes"
      - 'periodo': None | "(Acumulado)" | "YYYY-MM"
      - 'df_view': DataFrame pronto para consumo (filtrado ou agregado)
    """
    df = normalize_mes_column(df)
    if periodo is None or periodo == "(Todos)":
        return {"view": "mensal", "periodo": None, "df_view": df}
    if periodo == "(Acumulado)":
        # acumulado: agregação por somas (mantém colunas numéricas)
        agg = df.select_dtypes(include=["number"]).sum().to_frame().T
        # preservar mes_norm para indicar acumulado
        agg["mes_norm"] = "(Acumulado)"
        return {"view": "acumulado", "periodo": "(Acumulado)", "df_view": agg}
    # assume YYYY-MM
    mes = str(periodo).strip()[:7]
    df_mes = df[df["mes_norm"] == mes]
    return {"view": "mes", "periodo": mes, "df_view": df_mes}