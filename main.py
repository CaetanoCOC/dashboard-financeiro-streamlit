# main.py

import streamlit as st
import pandas as pd
import unicodedata
import json
import os
import altair as alt

# Configuração da página
st.set_page_config(
    page_title="Dashboard Financeiro",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("📊 Dashboard Financeiro")

# --- Funções de parsing e normalização ---
def parse_val(v):
    if pd.isna(v):
        return 0.0
    s = str(v).replace("R$", "").replace(" ", "")
    if "." in s and "," in s:
        s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0

def normalize(s: str) -> str:
    nk = unicodedata.normalize("NFD", str(s))
    no_acc = "".join(ch for ch in nk if unicodedata.category(ch) != "Mn")
    return no_acc.lower().strip()

def fmt_brl(v: float) -> str:
    s = f"{v:,.2f}"  # e.g. '1,234.56'
    return s.replace(",", "_").replace(".", ",").replace("_", ".")

# --- Configurações de metas ---
METAS_FILE = "metas.json"
desired_cats = [
    "Alimentação",
    "Nubank",
    "Transporte",
    "Lazer",
    "Clash of Clans"
]

def load_metas():
    if os.path.exists(METAS_FILE):
        with open(METAS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    return {cat: float(data.get(cat, 0.0)) for cat in desired_cats}

def save_metas(metas):
    with open(METAS_FILE, "w", encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False, indent=2)

metas = load_metas()

# --- Carregamento de dados com cache ---
# --- Upload e verificação ---
uploaded_file = st.file_uploader("📁 Envie sua planilha Excel de finanças", type=["xlsx"])

if uploaded_file is None:
    st.warning("Por favor, envie a planilha para visualizar o dashboard.")
    st.stop()

# --- Função com tratamento de erro ---
@st.cache_data(ttl=10)
def load_data(file):
    try:
        df = pd.read_excel(
            file,
            usecols="A:E",
            engine="openpyxl",
            converters={"valor": parse_val}
        ).dropna(subset=["data"])
        df["data"] = pd.to_datetime(df["data"], dayfirst=True)
        df["tipo"] = df["E/D"].apply(normalize)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        st.stop()

# --- Leitura final e feedback ---
df = load_data(uploaded_file)
st.success("✅ Planilha carregada com sucesso!")
st.dataframe(df.head())






df = load_data(uploaded_file)


# --- Total Disponível Acumulado (todos os meses) ---
total_entradas_all = df.loc[df["tipo"] == "entrada", "valor"].sum()
total_saidas_all   = df.loc[df["tipo"] == "saida",   "valor"].sum()
total_disponivel   = total_entradas_all - total_saidas_all
st.metric(
    label="💼 Total Disponível (acumulado)",
    value=f"R$ {fmt_brl(total_disponivel)}"
)

# --- Sidebar: Metas e Filtros ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Metas por Categoria")
for cat in desired_cats:
    metas[cat] = st.sidebar.number_input(
        label=f"Meta mensal ({cat})",
        min_value=0.0,
        value=metas.get(cat, 0.0),
        step=50.0,
        format="%.2f"
    )
save_metas(metas)

st.sidebar.markdown("---")
st.sidebar.header("Filtros")
anos = sorted(df["data"].dt.year.unique())
meses_map = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}
ano_sel = st.sidebar.selectbox("Ano", anos,
    index=anos.index(2025) if 2025 in anos else 0)
mes_sel = st.sidebar.selectbox(
    "Mês", list(meses_map.keys()),
    format_func=lambda x: meses_map[x],
    index=list(meses_map.keys()).index(mes_sel := max(meses_map.keys()))
)
mostrar_geral = st.sidebar.checkbox("Visão Geral Mensal", value=True)

# --- Filtra dados ---
mask = (df["data"].dt.year == ano_sel) & (df["data"].dt.month == mes_sel)
df_sel = df.loc[mask]

# --- Métricas Principais ---
entradas = df_sel.loc[df_sel["tipo"] == "entrada", "valor"].sum()
saidas   = df_sel.loc[df_sel["tipo"] == "saida",   "valor"].sum()
saldo    = entradas - saidas
c1, c2, c3 = st.columns(3)
c1.metric("💰 Entradas", f"R$ {fmt_brl(entradas)}")
c2.metric("💸 Saídas",   f"R$ {fmt_brl(saidas)}")
saldo_color = "green" if saldo >= 0 else "red"
c3.markdown(
    f"<div style='font-size:2rem; font-weight:bold;'>🧾 Saldo: "
    f"<span style='color:{saldo_color}'>R$ {fmt_brl(saldo)}</span></div>",
    unsafe_allow_html=True
)

# --- Gráfico de Gastos por Categoria ---
st.markdown("---")
st.subheader(f"Gastos por Categoria em {meses_map[mes_sel]}/{ano_sel}")
gasto_cat = (
    df_sel[df_sel["tipo"] == "saida"]
    .groupby("categoria")["valor"]
    .sum()
)
st.bar_chart(gasto_cat)

# --- Progresso de Metas Mensais ---
st.markdown("---")
st.subheader("📈 Progresso de Metas Mensais")
for cat in desired_cats:
    meta_val = metas.get(cat, 0.0)
    gasto_val = (
        df_sel[(df_sel["categoria"] == cat) & (df_sel["tipo"] == "saida")]
        ["valor"].sum()
    )
    progresso = gasto_val / meta_val if meta_val > 0 else 0.0
    st.write(f"**{cat}**:  {fmt_brl(gasto_val)} /  {fmt_brl(meta_val)}")
    st.progress(min(progresso, 1.0))
    if progresso >= 1.0:
        st.warning(f"Você estourou a meta de {cat}!")

# --- Visão Geral Mensal com cor customizada ---
if mostrar_geral:
    st.markdown("---")
    st.subheader("Visão Geral Mensal")

    # 1) Agrupa por mês e tipo
    monthly = (
        df
        .groupby([pd.Grouper(key="data", freq="M"), "tipo"])["valor"]
        .sum()
        .unstack(fill_value=0)
    )
    monthly.index = (
        monthly.index.to_period("M").strftime("%b/%Y")
    )

    # 2) Prepara DataFrame para Altair
    mdf = monthly.reset_index()
    idx_col = mdf.columns[0]
    mdf = mdf.rename(columns={idx_col: "periodo"})
    mdf = mdf.melt(id_vars="periodo", var_name="tipo", value_name="valor")

    # 3) Plota com Altair
    chart = (
        alt.Chart(mdf)
        .mark_line(point=True)
        .encode(
            x=alt.X("periodo:T", title="Mês"),
            y=alt.Y("valor:Q", title="Valor (R$)"),
            color=alt.Color(
                "tipo:N",
                scale=alt.Scale(
                    domain=["entrada", "saida"],
                    range=["#1f77b4", "red"]
                ),
                title="Tipo"
            )
        )
        .properties(width=800, height=300)
    )
    st.altair_chart(chart, use_container_width=True)

# --- Tabela de Lançamentos ---
st.markdown("---")
st.subheader("Lançamentos Detalhados")
st.dataframe(
    df_sel[["data", "categoria", "tipo", "valor", "descrição"]]
    .sort_values("data")
    .reset_index(drop=True)
)
