import math
import streamlit as st
import pandas as pd
from typing import Optional

from app.dashboards.utils import (
    pct,
    explain_kpi,
    format_brl,
    cached_quality_tag,
    metric_with_tooltip,
)


def _safe_sum(df: Optional[pd.DataFrame], col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    try:
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    except Exception:
        return 0.0


def _safe_mean(df: Optional[pd.DataFrame], col: str) -> Optional[float]:
    if df is None or df.empty or col not in df.columns:
        return None
    try:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        return float(vals.mean()) if not vals.empty else None
    except Exception:
        return None


def show_dre(df: Optional[pd.DataFrame], modo: str = "Resumido", mes: Optional[str] = None):
    """
    Exibe resumo da DRE.
    - df: DataFrame com linhas possivelmente mensais ou agregadas.
    - modo: "Resumido" ou "Detalhado".
    - mes: se fornecido (formato 'YYYY-MM' ou parseável), filtra o DataFrame para esse mês antes de agregar.
    Retorna dicionário com os valores calculados.
    """
    st.subheader("📑 Demonstração do Resultado do Exercício")

    if df is None:
        df = pd.DataFrame()

    # defensivo: remover colunas duplicadas que possam vir de merges/leitura
    if isinstance(df, pd.DataFrame) and not df.empty:
        df = df.loc[:, ~df.columns.duplicated()].copy()

    # Normalizar e criar mes_norm (YYYY-MM) robusto a formatos variados
    if "mes" in df.columns and not df.empty:
        # tentar parse via pandas; se falhar, fallback para slice(0,7)
        try:
            df["mes_norm"] = pd.to_datetime(df["mes"].astype(str), errors="coerce", dayfirst=False).dt.to_period("M").astype(str)
        except Exception:
            df["mes_norm"] = df["mes"].astype(str).str.strip().str.slice(0, 7)
        mask_na = df["mes_norm"].isna()
        if mask_na.any():
            df.loc[mask_na, "mes_norm"] = df.loc[mask_na, "mes"].astype(str).str.strip().str.slice(0, 7)
    else:
        # garantir a coluna para evitar KeyError mais adiante
        df["mes_norm"] = None

    # se mes foi solicitado, normalizar o valor e filtrar
    if mes:
        try:
            mes_norm = pd.to_datetime(str(mes).strip()[:7] + "-01", errors="coerce").to_period("M").astype(str)
        except Exception:
            mes_norm = str(mes).strip()[:7]
        if "mes_norm" in df.columns:
            df = df[df["mes_norm"] == mes_norm]
            if df.empty:
                st.warning(f"Sem dados da DRE para o mês {mes_norm}.")
                return {}
        else:
            st.warning("Não foi possível filtrar por mês: coluna 'mes' ausente na DRE.")
            return {}

    else:
        # sem mes: se tiver múltiplos meses, avisar que os valores são agregados
        if "mes_norm" in df.columns and df["mes_norm"].nunique() > 1:
            st.info("Visualizando DRE agregada para múltiplos meses.")
    # Agregados defensivos (agregam sobre o df já filtrado)
    receita_bruta = _safe_sum(df, "receita_bruta")
    deducoes = _safe_sum(df, "deducoes")
    receita_liquida = receita_bruta - deducoes

    cpv = _safe_sum(df, "custo_produto_vendido")
    # aceitar col alias "cpv" se existir
    if cpv == 0 and "cpv" in df.columns:
        cpv = _safe_sum(df, "cpv")
    csp = _safe_sum(df, "custo_servico_prestado")

    lucro_bruto = receita_liquida - (cpv + csp)

    desp_vendas = _safe_sum(df, "despesas_vendas")
    desp_admin = _safe_sum(df, "despesas_administrativas")
    outras_desp = _safe_sum(df, "outras_despesas")
    despesas_operacionais = desp_vendas + desp_admin + outras_desp
    lucro_operacional = lucro_bruto - despesas_operacionais

    rec_fin = _safe_sum(df, "receitas_financeiras")
    desp_fin = _safe_sum(df, "despesas_financeiras")
    resultado_financeiro = rec_fin - desp_fin

    lucro_antes_ir = lucro_operacional + resultado_financeiro
    ir = _safe_sum(df, "imposto_renda")
    lucro_liquido = lucro_antes_ir - ir

    # Percentuais e margens (pct retorna 0..100)
    ded_pct_bruta = pct(deducoes, receita_bruta)
    cpv_pct_rl = pct(cpv, receita_liquida)
    csp_pct_rl = pct(csp, receita_liquida)
    desp_op_pct_lb = pct(despesas_operacionais, lucro_bruto)

    margem_bruta = pct(lucro_bruto, receita_liquida)
    margem_operacional = pct(lucro_operacional, receita_liquida)
    margem_liquida = pct(lucro_liquido, receita_liquida)

    # Exibição principal (4x4 grid adaptado)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        explain_kpi("Receita Bruta", format_brl(receita_bruta), percent=ded_pct_bruta, base_label="Receita Bruta",
                    help_text="Total vendido antes de deduções.")
    with col2:
        explain_kpi("(-) Deduções", format_brl(deducoes), percent=ded_pct_bruta, base_label="Receita Bruta",
                    help_text="Impostos, devoluções e descontos.")
    with col3:
        explain_kpi("Receita Líquida", format_brl(receita_liquida),
                    help_text="Receita Bruta menos deduções.")
    with col4:
        explain_kpi("Lucro Bruto", format_brl(lucro_bruto), percent=margem_bruta, base_label="Receita Líquida",
                    help_text="Receita Líquida menos custos diretos (CPV/CSP).")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        explain_kpi("(-) Despesas Operacionais", format_brl(despesas_operacionais), percent=desp_op_pct_lb,
                    base_label="Lucro Bruto", help_text="Despesas com vendas, administrativas e outras.")
    with col6:
        explain_kpi("Resultado Financeiro", format_brl(resultado_financeiro),
                    help_text="Receitas financeiras menos despesas financeiras.")
    with col7:
        explain_kpi("Lucro Antes de IR", format_brl(lucro_antes_ir), percent=margem_operacional, base_label="Receita Líquida",
                    help_text="Lucro operacional ajustado pelo resultado financeiro.")
    with col8:
        explain_kpi("Lucro Líquido", format_brl(lucro_liquido), percent=margem_liquida, base_label="Receita Líquida",
                    help_text="Lucro final após impostos.",
                    color=("#16a34a" if lucro_liquido >= 0 else "#ef4444"))

    # Ajuda conceitual
    with st.expander("Como ler a DRE"):
        st.write(
            "- Receita Líquida = Receita Bruta − Deduções\n"
            "- Lucro Bruto = Receita Líquida − (CPV + CSP)\n"
            "- Lucro Operacional = Lucro Bruto − Despesas Operacionais\n"
            "- Lucro Líquido = Lucro Antes de IR − IR"
        )

    # Modo detalhado: gráfico de participação por conta + seleção de mês interativa
    if modo == "Detalhado":
        st.markdown("### 📊 Detalhamento")

        if df is None or df.empty:
            st.info("Sem dados de DRE para o período selecionado.")
            return {
                "receita_bruta": receita_bruta,
                "deducoes": deducoes,
                "receita_liquida": receita_liquida,
                "cpv": cpv,
                "csp": csp,
                "lucro_bruto": lucro_bruto,
                "despesas_operacionais": despesas_operacionais,
                "lucro_operacional": lucro_operacional,
                "resultado_financeiro": resultado_financeiro,
                "lucro_antes_ir": lucro_antes_ir,
                "ir": ir,
                "lucro_liquido": lucro_liquido
            }

        # preparar tabela mensal: se já estamos filtrados por mes, mostrar a linha; se não, mostrar por mes
        if "mes_norm" in df.columns and df["mes_norm"].nunique() > 1:
            # montar um resumo por mês (não re-agregar valores além do necessário)
            display_cols = [c for c in ["mes_norm", "receita_bruta", "deducoes",
                                        "custo_produto_vendido", "custo_servico_prestado", "despesas_vendas",
                                        "despesas_administrativas", "outras_despesas", "receitas_financeiras",
                                        "despesas_financeiras", "imposto_renda"] if c in df.columns]
            # agrupar por mes_norm para exibir um resumo mensal
            monthly = df.groupby("mes_norm", as_index=False)[[c for c in display_cols if c != "mes_norm"]].sum()
            # renomear coluna para exibição
            monthly = monthly.rename(columns={"mes_norm": "mes"})

            # seleção de mês interativa: AgGrid quando disponível, fallback para selectbox/botões
            try:
                from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
                use_ag = True
            except Exception:
                use_ag = False

            selected_month = None
            if use_ag:
                try:
                    gb = GridOptionsBuilder.from_dataframe(monthly)
                    gb.configure_selection(selection_mode="single", use_checkbox=False)
                    gb.configure_grid_options(domLayout="normal")
                    grid_opts = gb.build()
                    grid_resp = AgGrid(
                        monthly,
                        gridOptions=grid_opts,
                        height=300,
                        fit_columns_on_grid_load=True,
                        update_mode=GridUpdateMode.SELECTION_CHANGED,
                        data_return_mode=DataReturnMode.FILTERED
                    )
                    selected = grid_resp.get("selected_rows", [])
                    if selected:
                        sel = selected[0]
                        selected_month = sel.get("mes")
                    else:
                        st.info("Selecione um mês na tabela acima para ver os detalhes individuais.")
                except Exception:
                    use_ag = False

            if not use_ag:
                # fallback leve: selectbox (boa UX para many rows) + mostrar tabela
                months = monthly["mes"].astype(str).tolist()
                selected_month = st.selectbox("Selecione o mês para ver detalhes", options=months)
                # st.dataframe(monthly, use_container_width=True)

            # se um mês foi selecionado, renderizar composição daquele mês; senão, mostrar composição agregada por mês
            if selected_month:
                sel_mes = selected_month
                st.markdown(f"#### Composição do mês {sel_mes}")

                # df_month: linhas do df correspondentes ao mês selecionado
                df_month = df[df["mes_norm"] == sel_mes]

                # calcular base (preferir receita_liquida, senão receita_bruta)
                if "receita_liquida" in df_month.columns:
                    base = _safe_sum(df_month, "receita_liquida")
                    base_label = "Receita Líquida"
                elif "receita_bruta" in df_month.columns:
                    base = _safe_sum(df_month, "receita_bruta")
                    base_label = "Receita Bruta"
                else:
                    base = None
                    base_label = None

                # montar componentes
                vals = {}
                if "custo_produto_vendido" in df_month.columns:
                    vals["CPV"] = _safe_sum(df_month, "custo_produto_vendido")
                if "custo_servico_prestado" in df_month.columns:
                    vals["CSP"] = _safe_sum(df_month, "custo_servico_prestado")
                # despesas detalhadas
                if "despesas_vendas" in df_month.columns:
                    vals["Despesas Vendas"] = _safe_sum(df_month, "despesas_vendas")
                if "despesas_administrativas" in df_month.columns:
                    vals["Despesas Administrativas"] = _safe_sum(df_month, "despesas_administrativas")
                if "outras_despesas" in df_month.columns:
                    vals["Outras Despesas"] = _safe_sum(df_month, "outras_despesas")
                # resultado financeiro
                rec_fin = _safe_sum(df_month, "receitas_financeiras")
                desp_fin = _safe_sum(df_month, "despesas_financeiras")
                if ("receitas_financeiras" in df_month.columns) or ("despesas_financeiras" in df_month.columns):
                    vals["Resultado Financeiro"] = rec_fin - desp_fin
                if "imposto_renda" in df_month.columns:
                    vals["IR"] = _safe_sum(df_month, "imposto_renda")

                # agregar Despesas Operacionais como soma das subcontas se existirem
                desp_ops = 0.0
                for k in ["Despesas Vendas", "Despesas Administrativas", "Outras Despesas"]:
                    desp_ops += float(vals.get(k, 0.0))
                if desp_ops:
                    vals["Despesas Operacionais"] = desp_ops

                # preparar DataFrame de componentes
                comp_rows = []
                for k, v in vals.items():
                    if v is None or abs(v) == 0:
                        continue
                    comp_rows.append({"conta": k, "valor": float(v)})

                if not comp_rows or base in (None, 0):
                    st.info("Dados insuficientes para calcular participação percentual (falta base de receita ou componentes).")
                else:
                    comp_pd = pd.DataFrame(comp_rows)
                    comp_pd["pct"] = comp_pd["valor"] / float(base) * 100.0
                    comp_pd["abs_val"] = comp_pd["valor"].abs()
                    comp_pd = comp_pd.sort_values("abs_val", ascending=False).reset_index(drop=True)

                    # plot: try plotly, fallback para st.bar_chart
                    try:
                        import plotly.graph_objects as go
                        colors = ["#ef4444" if v < 0 else "#16a34a" for v in comp_pd["valor"]]
                        fig_pie = go.Figure(go.Pie(
                            labels=comp_pd["conta"],
                            values=comp_pd["abs_val"],
                            hole=0.4,
                            hovertemplate="%{label}<br>Valor: %{value:.2f}<br>Participação: %{percent}",
                            textinfo="label+percent"
                        ))
                        fig_pie.update_layout(title_text=f"Participação por conta — base: {base_label}")

                        fig_bar = go.Figure()
                        fig_bar.add_trace(go.Bar(
                            x=comp_pd["conta"],
                            y=comp_pd["valor"],
                            marker_color=colors,
                            text=[f"{pct:.1f}%" for pct in comp_pd["pct"]],
                            textposition="auto",
                            hovertemplate="<b>%{x}</b><br>Valor: %{y:.2f}<br>Participação: %{text}"
                        ))
                        fig_bar.update_layout(title_text="Contribuição por conta (valores e percentuais)", yaxis_title="Valor (R$)")

                        col_a, col_b = st.columns([1, 1])
                        with col_a:
                            st.plotly_chart(fig_pie, use_container_width=True)
                        with col_b:
                            st.plotly_chart(fig_bar, use_container_width=True)

                        st.table(comp_pd[["conta", "valor", "pct"]].assign(
                            valor=lambda d: d["valor"].map(lambda x: f"R$ {x:,.2f}"),
                            pct=lambda d: d["pct"].map(lambda x: f"{x:.2f}%")
                        ).rename(columns={"conta": "Conta", "valor": "Valor", "pct": "% da base"}))
                    except Exception:
                        st.info("Plotly não disponível — exibindo gráfico de barras simples.")
                        simple = comp_pd.set_index("conta")[["valor", "pct"]]
                        st.bar_chart(simple["valor"])
                        st.dataframe(simple.style.format({"valor": "{:,.2f}", "pct": "{:.2f}%"}), use_container_width=True)

            else:
                # sem mês selecionado: mostrar gráfico de participação acumulada por mês para a base escolhida
                st.markdown("#### Visão mensal (selecione um mês para ver a composição)")

                # preparar base por mês (preferir receita_liquida)
                if "receita_liquida" in monthly.columns:
                    base_col = "receita_liquida"
                elif "receita_bruta" in monthly.columns:
                    base_col = "receita_bruta"
                else:
                    base_col = None

                # calcular componentes por mês (CPV, CSP, Despesas Operacionais, Resultado Financeiro, IR)
                comps = []
                for _, row in monthly.iterrows():
                    row_dict = row.to_dict()
                    mes_label = row_dict.get("mes")
                    # base
                    base_val = row_dict.get(base_col) if base_col else None
                    # contas
                    cpv_v = row_dict.get("custo_produto_vendido", 0.0)
                    csp_v = row_dict.get("custo_servico_prestado", 0.0)
                    dv_v = row_dict.get("despesas_vendas", 0.0)
                    da_v = row_dict.get("despesas_administrativas", 0.0)
                    od_v = row_dict.get("outras_despesas", 0.0)
                    rec_fin_v = row_dict.get("receitas_financeiras", 0.0)
                    desp_fin_v = row_dict.get("despesas_financeiras", 0.0)
                    ir_v = row_dict.get("imposto_renda", 0.0)

                    desp_ops_v = (dv_v or 0.0) + (da_v or 0.0) + (od_v or 0.0)
                    res_fin_v = (rec_fin_v or 0.0) - (desp_fin_v or 0.0)

                    comps.append({
                        "mes": mes_label,
                        "CPV": float(cpv_v or 0.0),
                        "CSP": float(csp_v or 0.0),
                        "Despesas Operacionais": float(desp_ops_v),
                        "Resultado Financeiro": float(res_fin_v),
                        "IR": float(ir_v or 0.0),
                        "base": float(base_val or 0.0)
                    })

                comps_df = pd.DataFrame(comps)
                if base_col is None or comps_df["base"].eq(0).all():
                    st.info("Dados insuficientes para visão mensal (sem base de receita).")
                else:
                    # calcular pct por mês e desenhar barras empilhadas (plotly) ou múltiplas barras
                    try:
                        import plotly.express as px
                        # normalizar para percentuais relativos à base
                        pct_df = comps_df.melt(id_vars=["mes", "base"], value_vars=["CPV", "CSP", "Despesas Operacionais", "Resultado Financeiro", "IR"], var_name="conta", value_name="valor")
                        pct_df["pct"] = pct_df["valor"] / pct_df["base"] * 100.0
                        fig = px.bar(pct_df, x="mes", y="pct", color="conta", title=f"Participação percentual por conta (base: {base_col})", labels={"pct": "% da base", "mes": "Mês"})
                        st.plotly_chart(fig, use_container_width=True)
                        st.dataframe(comps_df.set_index("mes").style.format("{:,.2f}"), use_container_width=True)
                    except Exception:
                        # fallback simples: mostrar tabela com percentuais
                        comps_df["CPV_pct"] = comps_df["CPV"] / comps_df["base"] * 100.0
                        comps_df["CSP_pct"] = comps_df["CSP"] / comps_df["base"] * 100.0
                        comps_df["DespOper_pct"] = comps_df["Despesas Operacionais"] / comps_df["base"] * 100.0
                        comps_df["ResFin_pct"] = comps_df["Resultado Financeiro"] / comps_df["base"] * 100.0
                        comps_df["IR_pct"] = comps_df["IR"] / comps_df["base"] * 100.0
                        st.dataframe(comps_df.set_index("mes")[["CPV_pct","CSP_pct","DespOper_pct","ResFin_pct","IR_pct"]].style.format("{:.2f}%"), use_container_width=True)

        else:
            # se já está filtrado pra um único mês, mostrar composição diretamente (mes individual)
            display_cols = [c for c in ["mes", "receita_bruta", "deducoes", "receita_liquida",
                                        "custo_produto_vendido", "custo_servico_prestado", "despesas_vendas",
                                        "despesas_administrativas", "outras_despesas", "receitas_financeiras",
                                        "despesas_financeiras", "imposto_renda"] if c in df.columns]
            # exibir tabela resumida e também gráfico de composição daquele mês
            st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)

            # compor df_month igual ao bloco de seleção acima (usar df já filtrado)
            df_month = df.copy()
            if "receita_liquida" in df_month.columns:
                base = _safe_sum(df_month, "receita_liquida")
                base_label = "Receita Líquida"
            elif "receita_bruta" in df_month.columns:
                base = _safe_sum(df_month, "receita_bruta")
                base_label = "Receita Bruta"
            else:
                base = None
                base_label = None

            vals = {}
            if "custo_produto_vendido" in df_month.columns:
                vals["CPV"] = _safe_sum(df_month, "custo_produto_vendido")
            if "custo_servico_prestado" in df_month.columns:
                vals["CSP"] = _safe_sum(df_month, "custo_servico_prestado")
            if "despesas_vendas" in df_month.columns:
                vals["Despesas Vendas"] = _safe_sum(df_month, "despesas_vendas")
            if "despesas_administrativas" in df_month.columns:
                vals["Despesas Administrativas"] = _safe_sum(df_month, "despesas_administrativas")
            if "outras_despesas" in df_month.columns:
                vals["Outras Despesas"] = _safe_sum(df_month, "outras_despesas")
            rec_fin = _safe_sum(df_month, "receitas_financeiras")
            desp_fin = _safe_sum(df_month, "despesas_financeiras")
            if ("receitas_financeiras" in df_month.columns) or ("despesas_financeiras" in df_month.columns):
                vals["Resultado Financeiro"] = rec_fin - desp_fin
            if "imposto_renda" in df_month.columns:
                vals["IR"] = _safe_sum(df_month, "imposto_renda")

            desp_ops = 0.0
            for k in ["Despesas Vendas", "Despesas Administrativas", "Outras Despesas"]:
                desp_ops += float(vals.get(k, 0.0))
            if desp_ops:
                vals["Despesas Operacionais"] = desp_ops

            comp_rows = []
            for k, v in vals.items():
                if v is None or abs(v) == 0:
                    continue
                comp_rows.append({"conta": k, "valor": float(v)})

            if not comp_rows or base in (None, 0):
                st.info("Dados insuficientes para calcular participação percentual (falta base de receita ou componentes).")
            else:
                comp_pd = pd.DataFrame(comp_rows)
                comp_pd["pct"] = comp_pd["valor"] / float(base) * 100.0
                comp_pd["abs_val"] = comp_pd["valor"].abs()
                comp_pd = comp_pd.sort_values("abs_val", ascending=False).reset_index(drop=True)

                try:
                    import plotly.graph_objects as go
                    colors = ["#ef4444" if v < 0 else "#16a34a" for v in comp_pd["valor"]]
                    fig_pie = go.Figure(go.Pie(
                        labels=comp_pd["conta"],
                        values=comp_pd["abs_val"],
                        hole=0.4,
                        hovertemplate="%{label}<br>Valor: %{value:.2f}<br>Participação: %{percent}",
                        textinfo="label+percent"
                    ))
                    fig_pie.update_layout(title_text=f"Participação por conta — base: {base_label}")

                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        x=comp_pd["conta"],
                        y=comp_pd["valor"],
                        marker_color=colors,
                        text=[f"{pct:.1f}%" for pct in comp_pd["pct"]],
                        textposition="auto",
                        hovertemplate="<b>%{x}</b><br>Valor: %{y:.2f}<br>Participação: %{text}"
                    ))
                    fig_bar.update_layout(title_text="Contribuição por conta (valores e percentuais)", yaxis_title="Valor (R$)")

                    col_a, col_b = st.columns([1, 1])
                    with col_a:
                        st.plotly_chart(fig_pie, use_container_width=True)
                    with col_b:
                        st.plotly_chart(fig_bar, use_container_width=True)

                    st.table(comp_pd[["conta", "valor", "pct"]].assign(
                        valor=lambda d: d["valor"].map(lambda x: f"R$ {x:,.2f}"),
                        pct=lambda d: d["pct"].map(lambda x: f"{x:.2f}%")
                    ).rename(columns={"conta": "Conta", "valor": "Valor", "pct": "% da base"}))
                except Exception:
                    st.info("Plotly não disponível — exibindo gráfico de barras simples.")
                    simple = comp_pd.set_index("conta")[["valor", "pct"]]
                    st.bar_chart(simple["valor"])
                    st.dataframe(simple.style.format({"valor": "{:,.2f}", "pct": "{:.2f}%"}), use_container_width=True)

    # Modo resumido já exibido acima (KPIs). Se desejado, retornar os valores calculados para usos programáticos
    return {
        "receita_bruta": receita_bruta,
        "deducoes": deducoes,
        "receita_liquida": receita_liquida,
        "cpv": cpv,
        "csp": csp,
        "lucro_bruto": lucro_bruto,
        "despesas_operacionais": despesas_operacionais,
        "lucro_operacional": lucro_operacional,
        "resultado_financeiro": resultado_financeiro,
        "lucro_antes_ir": lucro_antes_ir,
        "ir": ir,
        "lucro_liquido": lucro_liquido
    }