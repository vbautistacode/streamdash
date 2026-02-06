# ml/train_model.py
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from ml.sample_data import generate_financial_series

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "isolation_forest.joblib")

def prepare_features(df: pd.DataFrame) -> np.ndarray:
    f = df.copy()
    for c in ["receita", "ebitda", "margem_liquida", "roi"]:
        if c in f.columns:
            f[c] = pd.to_numeric(f[c], errors="coerce").fillna(0.0)
        else:
            f[c] = 0.0
    return f[["receita", "ebitda", "margem_liquida", "roi"]].values

def train_and_save(df: pd.DataFrame = None, contamination: float = 0.05, random_state: int = 42) -> str:
    if df is None:
        df = generate_financial_series()
    X = prepare_features(df)
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("iforest", IsolationForest(n_estimators=200, contamination=contamination, random_state=random_state))
    ])
    pipeline.fit(X)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Modelo salvo em {MODEL_PATH}")
    return MODEL_PATH

if __name__ == "__main__":
    train_and_save()

#Treine: python -m ml.train_model