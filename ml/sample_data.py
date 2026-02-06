# ml/sample_data.py
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Tuple

def generate_financial_series(start: str = "2024-01-01", months: int = 24, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range(start=start, periods=months, freq="MS")
    base_revenue = np.linspace(100000, 150000, months)
    noise = np.random.normal(0, 5000, months)
    receita = base_revenue + noise
    margem = np.clip(np.random.normal(0.12, 0.03, months), 0, 1)
    ebitda = receita * margem
    roi = np.random.normal(0.08, 0.02, months)
    df = pd.DataFrame({
        "mes": dates.strftime("%Y-%m"),
        "mes_dt": dates,
        "receita": receita,
        "margem_liquida": margem,
        "ebitda": ebitda,
        "roi": roi
    })
    # inserir alguns outliers para teste
    if months > 6:
        df.loc[5, "receita"] *= 0.6
    if months > 12:
        df.loc[12, "ebitda"] *= 0.2
    return df

def generate_contabeis_series(start: str = "2024-01-01", months: int = 24, seed: int = 43) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range(start=start, periods=months, freq="MS")
    patrimonio = np.linspace(500000, 600000, months) + np.random.normal(0, 10000, months)
    valor_mercado = patrimonio * (1.2 + np.random.normal(0, 0.1, months))
    df = pd.DataFrame({
        "mes": dates.strftime("%Y-%m"),
        "mes_dt": dates,
        "patrimonio_liquido": patrimonio,
        "valor_mercado": valor_mercado,
        "tipo_empresa": ["aberta"] * months
    })
    return df

if __name__ == "__main__":
    fin = generate_financial_series()
    cont = generate_contabeis_series()
    fin.to_csv("ml/sample_fin.csv", index=False)
    cont.to_csv("ml/sample_cont.csv", index=False)
    print("Amostras geradas em ml/sample_fin.csv e ml/sample_cont.csv")

#Gere dados: python -m ml.sample_data