# etl/validations.py
import pandas as pd
from typing import Optional

def validate_financial_df(df: pd.DataFrame, tenant_col: str = "tenant_id") -> pd.DataFrame:
    """
    Valida e anota o DataFrame financeiro com flags úteis para ETL.
    Adiciona colunas:
      - validation_flag: string com motivo (missing_critical, duplicate, large_delta)
      - receita_pct_change: variação mês a mês da receita
    """
    if df is None:
        return pd.DataFrame()

    df = df.copy()

    # garantir colunas numéricas
    for c in ["receita", "ebitda", "margem_liquida", "roi"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # inicializa coluna de flag
    if "validation_flag" not in df.columns:
        df["validation_flag"] = None

    # checar nulos críticos
    critical_mask = df[["mes", "receita", "ebitda"]].isna().any(axis=1)
    df.loc[critical_mask, "validation_flag"] = df.loc[critical_mask, "validation_flag"].fillna("") + "missing_critical;"

    # checar duplicatas por tenant+mes
    if tenant_col in df.columns and "mes" in df.columns:
        dup_mask = df.duplicated(subset=[tenant_col, "mes"], keep=False)
        df.loc[dup_mask, "validation_flag"] = df.loc[dup_mask, "validation_flag"].fillna("") + "duplicate;"

    # delta month-over-month por tenant
    if tenant_col in df.columns and "receita" in df.columns:
        df = df.sort_values([tenant_col, "mes"])
        df["receita_pct_change"] = df.groupby(tenant_col)["receita"].pct_change()
        large_delta_mask = df["receita_pct_change"].abs() > 0.5
        df.loc[large_delta_mask, "validation_flag"] = df.loc[large_delta_mask, "validation_flag"].fillna("") + "large_delta;"

    # limpeza final: transformar "" em None
    df["validation_flag"] = df["validation_flag"].apply(lambda x: x if pd.notna(x) and x != "" else None)

    return df