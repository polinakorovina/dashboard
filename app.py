import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta

# 1) Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2) BI-стиль
st.markdown(
    """
    <style>
    .stApp { background-color: #F7F2FA; }
    [data-testid="stSidebar"] { background-color: #A485E0; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }

    .main-header { font-size: 34px; font-weight: 800; color: #1A1C1E; margin: 4px 0 18px 0; }
    .card-header { font-size: 18px; font-weight: 700; color: #1A1C1E; display: inline-block; }

    .kpi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .kpi-title { font-size: 16px; font-weight: 600; color: #1A1C1E; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
    .kpi-value { font-size: 36px; font-weight: 500; color: #6244BB; line-height: 1.2; }
    
    .bi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    .hint-icon {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        width: 18px;
        height: 18px;
        background-color: #E6E9EF;
        color: #7E8694;
        border-radius: 50%;
        font-size: 12px;
        font-weight: bold;
        cursor: help;
        position: relative;
        margin-left: 8px;
    }

    .hint-icon:hover::after {
        content: attr(data-hint);
        position: absolute;
        bottom: 125%; left: 50%; transform: translateX(-50%);
        background-color: #1A1C1E; color: #fff;
        padding: 8px 12px; border-radius: 8px;
        font-size: 12px; width: 200px; z-index: 1000;
        font-weight: normal;
    }
    
    /* Стили для таблицы без заголовка */
    .no-header-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
    }
    .no-header-table td {
        padding: 12px 15px;
        border-bottom: 1px solid #F0F2F6;
        color: #1A1C1E;
        font-size: 14px;
    }
    .no-header-table tr:last-child td { border-bottom: none; }
    .no-header-table tr:hover { background-color: #F8F9FB; }

    .block-container { padding-top: 1.7rem !important; }
    </style>
    """,
    unsafe_allow_html=True
)

def kpi_card(title: str, value: str, hint: str = ""):
    hint_html = f'<span class="hint-icon" data-hint="{hint}">?</span>' if hint else ""
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">{title} {hint_html}</div><div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)

# 3) Данные
TOKEN = os.getenv("YANDEX_TOKEN")
y = yadisk.YaDisk(token=TOKEN)
DB_PATH = "/Data/my_database.db"

@st.cache_data(ttl=600)
def load_data():
    if not y.exists(DB_PATH): return pd.DataFrame()
    y.download(DB_PATH, "local_view.db")
    conn = sqlite3.connect("local_view.db")
    df = pd.read_sql("SELECT * FROM tasks", conn)
    conn.close()
    if "Дата создания" not in df.columns: return pd.DataFrame()
    df["Дата создания"] = pd.to_datetime(df["Дата создания"], errors="coerce")
    df = df.dropna(subset=["Дата создания"])
    stages = ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]
    for col in stages: df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
    df["ttm_days"] = df[stages].sum(axis=1) / 1440
    df["cycle_time"] = df[["Бэклог разработки", "В работе"]].sum(axis=1) / 1440
    df["Резолюция"] = df.get("Резолюция", "Не указано").fillna("Не указано")
    df["Компоненты"] = df.get("Компоненты", "Не указано").fillna("Не указано")
    df["Приоритет"] = df.get("Приоритет", "Средний").fillna("Средний")
    return df

df = load_data()
if df.empty: st.stop()

# --- САЙДБАР ---
db_min, db_max = df["Дата создания"].min().date(), df["Дата создания"].max().date()
date_range = st.sidebar.date_input("Период анализа", value=(db_max - timedelta(days=7), db_max))
if not (isinstance(date_range, tuple) and len(date_range) == 2): st.stop()

start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
all_teams = sorted(df["Компоненты"].unique().tolist())
sel_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams)
sel_res = st.sidebar.multiselect("Резолюции", sorted(df["Резолюция"].unique().tolist()), default=sorted(df["Резолюция"].unique().tolist()))

f_df = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d) & 
          (df["Компоненты"].isin(sel_teams)) & (df["Резолюция"].isin(sel_res))].copy()

# --- ВЕРСТКА ---
st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4, gap="small")
with k1: kpi_card("Всего задач", f"{len(f_df)}", "За период")
with k2: kpi_card("TTM в днях", f"{(f_df['ttm_days'].mean() if len(f_df) else 0):.2f}", "Средний TTM")
with k3: kpi_card("Cycle time (дн)", f"{(f_df['cycle_time'].mean() if len(f_df) else 0):.2f}", "Средний Cycle Time")
with k4: 
    crit_late = len(f_df[(f_df["Резолюция"] == "Позже") & (f_df["Приоритет"] == "Критичный")])
    kpi_card("Критичные позже", f"{crit_late}", "Криты со статусом Позже")

st.write("")

c1, c2 = st.columns(2, gap="large")
t_order = f_df["Компоненты"].value_counts().index.tolist()

with c1:
    st.markdown('<div class="bi-card"><div class="card-header">Нагрузка по командам</div><span class="hint-icon" data-hint="Задачи по командам">?</span>', unsafe_allow_html=True)
    t_counts = f_df.groupby(["Компоненты", "Резолюция"]).size().reset_index(name="Кол-во")
    fig_l = px.bar(t_counts, x="Кол-во", y="Компоненты", color="Резолюция", orientation="h", text="Кол-во",
                   category_orders={"Компоненты": t_order}, color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"}, template="plotly_white")
    fig_l.update_layout(height=300, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig_l, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown('<div class="bi-card"><div class="card-header">Среднее время работы</div><span class="hint-icon" data-hint="TTM в днях">?</span>', unsafe_allow_html=True)
    t_avg = f_df.groupby("Компоненты")["ttm_days"].mean().reset_index()
    fig_a = px.bar(t_avg, x="ttm_days", y="Компоненты", orientation="h", text_auto=".1f",
                   color_discrete_sequence=["#6244BB"], template="plotly_white", category_orders={"Компоненты": t_order})
    fig_a.update_layout(height=300, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig_a, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="bi-card">', unsafe_allow_html=True)
dh1, dh2 = st.columns([5, 1])
with dh1: st.markdown('<div class="card-header">Динамика поступления задач</div><span class="hint-icon" data-hint="Новые задачи">?</span>', unsafe_allow_html=True)
with dh2: unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], label_visibility="collapsed")
resampled = f_df.set_index("Дата создания").resample({"День": "D", "Неделя": "W", "Месяц": "ME"}[unit]).size().reset_index(name="Задач")
fig_d = px.line(resampled, x="Дата создания", y="Задач", markers=True, color_discrete_sequence=["#6244BB"], template="plotly_white")
fig_d.update_layout(height=300, xaxis_title=None, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig_d, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# --- ТАБЛИЦА БЕЗ ЗАГОЛОВКА ---
df_period_res = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d) & (df["Резолюция"].isin(sel_res))]
active_teams_in_period = df_period_res["Компоненты"].unique()
inactive_teams = sorted([team for team in all_teams if team not in active_teams_in_period])

st.markdown('<div class="bi-card">', unsafe_allow_html=True)
st.markdown('<div class="card-header">Команды без задач за период</div><span class="hint-icon" data-hint="Команды без активности в БД">?</span>', unsafe_allow_html=True)

if inactive_teams:
    # Формируем HTML таблицу вручную для полного контроля
    rows = "".join([f"<tr><td>{team}</td></tr>" for team in inactive_teams])
    html_table = f'<table class="no-header-table">{rows}</table>'
    st.markdown(html_table, unsafe_allow_html=True)
else:
    st.info("Все команды активны.")
st.markdown("</div>", unsafe_allow_html=True)
