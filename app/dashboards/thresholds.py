# app/dashboards/thresholds.py

"""
Thresholds e helpers para qualidade de KPIs.
Fornece:
 - THRESH: dicionário compatível com código legado.
 - get_thresholds_for(kpi): retorna um dicionário com valores nominados.
 - get_prefer_high(kpi): indica se maior valor é melhor para o KPI.
"""

from typing import Dict, Any, Optional

# Mantemos a estrutura legada (tuplas) para compatibilidade.
# Formato leg legacy: (low, mid, high) ou (alerta, medio, bom) conforme código antigo.
THRESH: Dict[str, tuple] = {
    "roi": (0.10, 0.20, 0.20),
    "roe": (0.08, 0.15, 0.15),
    "margem_liquida": (0.05, 0.12, 0.12),
    "liquidez_corrente": (1.0, 1.5, 1.5),
    # divida_ebitda: menor é melhor — mantemos valores de referência
    "divida_ebitda": (2.0, 3.0, 2.0),
    "cagr": (0.05, 0.15, 0.15),
    "churn_rate": (0.02, 0.05, 0.10),
    "cac": (0.0, 0.0, 0.0),
}

# Modern wrapper: retorna um dicionário com chaves explicitas para facilitar uso.
def get_thresholds_for(kpi: str) -> Dict[str, float]:
    """
    Retorna thresholds nomeados para o KPI.
    Exemplo de retorno:
      { "low": 0.05, "mid": 0.12, "high": 0.12, "bom": 0.12, "alerta": 0.05 }
    Usa valores default quando KPI não encontrado.
    """
    raw = THRESH.get(kpi)
    if not raw or not isinstance(raw, (list, tuple)):
        # valores default defensivos
        return {"low": 0.0, "mid": 0.0, "high": 0.0, "bom": 0.0, "alerta": 0.0}
    # normalizar tupla de 3 elementos para um dict
    low, mid, high = raw[0], raw[1], raw[2]
    # definimos "bom" como high e "alerta" como mid (ajuste conforme necessidade)
    return {"low": float(low), "mid": float(mid), "high": float(high), "bom": float(high), "alerta": float(mid)}

def get_prefer_high(kpi: str) -> bool:
    """
    Indica se para o KPI maior valor é melhor.
    Por padrão assume True; alguns KPIs (ex.: divida_ebitda, churn_rate, cac) preferem menor.
    """
    lower_is_better = {"divida_ebitda", "churn_rate", "cac"}
    return False if kpi in lower_is_better else True

# Backwards compatibility helper for old code that expects thresholds as tuple
def thresholds_tuple(kpi: str) -> Optional[tuple]:
    return THRESH.get(kpi)

# Expor nomes para import direto (compat com `from ... import THRESH`)
__all__ = ["THRESH", "get_thresholds_for", "get_prefer_high", "thresholds_tuple"]