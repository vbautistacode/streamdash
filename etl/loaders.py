import pandas as pd

def load_csv(file):
    df = pd.read_csv(file)
    df.columns = df.columns.str.strip().str.lower()  # padroniza nomes
    return df

def load_excel(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip().str.lower()
    return df