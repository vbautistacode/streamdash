# app/dashboards/utils.py

import math
import streamlit as st
from typing import Optional, Dict, Any

# importa utilitários de thresholds
from app.dashboards.thresholds import get_thresholds_for, get_prefer_high

# -----------------------------
# Caching para funções puras (pequenas, mas úteis em UI)
# -----------------------------
@st.cache_data
def cached_pct(part, total):
    return pct(part, total)

@st.cache_data
def cached_format_brl(value):
    return format_brl(value)

@st.cache_data
def cached_quality_tag(value, kpi_name: Optional[str] = None, thresholds: Optional[Dict[str, float]] = None, prefer_high: Optional[bool] = None):
    """
    Wrapper cacheado que aceita opcionalmente o nome do KPI para buscar thresholds automáticos.
    - kpi_name: chave usada em thresholds.get_thresholds_for(kpi_name)
    - thresholds: se fornecido, tem precedência sobre thresholds automáticos
    - prefer_high: se fornecido, sobrescreve prefer_high automático
    """
    # resolve thresholds/prefer_high a partir do nome do KPI quando necessário
    if thresholds is None and kpi_name:
        auto = get_thresholds_for(kpi_name)
        if auto:
            thresholds = auto
    if prefer_high is None and kpi_name:
        prefer_high = get_prefer_high(kpi_name)
    return quality_tag(value, thresholds=thresholds, prefer_high=prefer_high)

# -----------------------------
# Básicos
# -----------------------------
def pct(part, total):
    """Retorna percentual seguro (0..100). Evita divisão por zero; retorna 0.0 em casos inválidos."""
    try:
        if part is None or total is None:
            return 0.0
        total = float(total)
        if total == 0:
            return 0.0
        return float(part) / total * 100.0
    except Exception:
        return 0.0

def format_brl(value):
    """Formata valores numéricos em R$ com separador de milhar; retorna '—' para None/NaN."""
    try:
        if value is None:
            return "—"
        val = float(value)
        if math.isnan(val):
            return "—"
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)

def _format_percent(value, precision=1):
    try:
        if value is None:
            return "—"
        v = float(value)
        if math.isnan(v):
            return "—"
        return f"{v:.{precision}f}%"
    except Exception:
        return str(value)

# -----------------------------
# explain_kpi
# -----------------------------
def explain_kpi(title, value, percent=None, base_label=None, help_text=None, color=None, formatter=None):
    """
    Renderiza um KPI com título, valor formatado e (opcional) percentual explicativo.
    - formatter: função(value) -> str para formatar o valor (ex.: format_brl). Se None, usa format_brl para numéricos.
    """
    col_title, col_val = st.columns([2, 1])

    style = f"font-weight:bold;{f' color:{color};' if color else ''}"
    col_title.markdown(f"<div style='{style}'>{title}</div>", unsafe_allow_html=True)

    fmt = formatter if callable(formatter) else (format_brl if isinstance(value, (int, float)) else str)
    try:
        display_val = fmt(value)
    except Exception:
        display_val = str(value)

    col_val.markdown(f"<div style='text-align:right'>{display_val}</div>", unsafe_allow_html=True)

    if percent is not None:
        try:
            p = float(percent)
            if p <= 1:
                p = p * 100.0
            caption = f"{p:.1f}%"
            if base_label:
                caption = f"{caption} de {base_label}"
            st.caption(caption)
        except Exception:
            st.caption(str(percent))

    if help_text:
        with st.expander("Entenda este indicador"):
            st.write(help_text)

# -----------------------------
# Quality tagging (retorna label, tag, color)
# -----------------------------
def _default_quality_colors():
    return {"bom": "#16a34a", "alerta": "#f59e0b", "ruim": "#ef4444", "unknown": "#9ca3af"}

def quality_tag(value, thresholds: Optional[Dict[str, float]] = None, prefer_high: Optional[bool] = True, kpi_name: Optional[str] = None):
    """
    Retorna (label, tag_key, color).
    - thresholds: dict com chaves 'bom' e 'alerta' (valores numéricos).
      Pode ser em 0..1 (fração) ou 0..100 (percent); a função tenta normalizar.
    - prefer_high: True se valores maiores são melhores; False se menores são melhores.
    - kpi_name: opcional, se fornecido e thresholds não passado, busca thresholds automáticos via get_thresholds_for.
    - label: string formatada do valor (em % se entre 0..1).
    - tag_key: 'bom' | 'alerta' | 'ruim'
    - color: código CSS hex associado
    """
    if value is None:
        return ("—", None, _default_quality_colors()["unknown"])

    try:
        v = float(value)
        if math.isnan(v):
            return ("—", None, _default_quality_colors()["unknown"])
    except Exception:
        return (str(value), None, _default_quality_colors()["unknown"])

    # se thresholds não fornecido, tentar buscar por kpi_name
    if thresholds is None and kpi_name:
        auto = get_thresholds_for(kpi_name)
        if auto:
            thresholds = auto

    # se prefer_high não fornecido, pegar do mapa quando kpi_name informado
    if prefer_high is None and kpi_name:
        prefer_high = get_prefer_high(kpi_name)

    if not thresholds:
        thresholds = {"bom": 0.7, "alerta": 0.4}

    def _normalize_threshold(t):
        if t is None:
            return None
        try:
            t = float(t)
            if t > 1 and v <= 1:
                return t / 100.0
            return t
        except Exception:
            return None

    bom_n = _normalize_threshold(thresholds.get("bom"))
    alerta_n = _normalize_threshold(thresholds.get("alerta"))

    tag = "ruim"
    if prefer_high:
        if bom_n is not None and v >= bom_n:
            tag = "bom"
        elif alerta_n is not None and v >= alerta_n:
            tag = "alerta"
    else:
        if bom_n is not None and v <= bom_n:
            tag = "bom"
        elif alerta_n is not None and v <= alerta_n:
            tag = "alerta"

    # label formatado
    if 0 <= v <= 1:
        label = f"{v*100:.1f}%"
    else:
        label = f"{v:.2f}"

    colors = _default_quality_colors()
    color = colors.get(tag, colors["unknown"])

    return (label, tag, color)

# -----------------------------
# Métrica com tooltip
# -----------------------------
def metric_with_tooltip(label, value, tooltip=None, tag_key=None, formatter=None):
    """
    Exibe uma métrica com tooltip explicativo e marcador de qualidade.
    - tag_key: string curta para exibir ao lado do valor (ex.: "●", "✔")
    """
    fmt = formatter if callable(formatter) else (format_brl if isinstance(value, (int, float)) else str)
    try:
        disp = fmt(value)
    except Exception:
        disp = str(value)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{label}**")
        if tooltip:
            st.caption(f"ℹ️ {tooltip}")
    with col2:
        txt = f"{disp} {tag_key}" if tag_key else disp
        st.markdown(f"<div style='text-align:right'>{txt}</div>", unsafe_allow_html=True)