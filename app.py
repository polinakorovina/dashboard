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
    .stApp { background-color: #F8F9FB; }
    [data-testid="stSidebar"] { background-color: #A485E0; color: white; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
        color: white !important;
    }
    .main-header { font-size: 34px; font-weight: 800; color: #1A1C1E; margin: 4px 0 18px 0; }
    .card-header { font-size: 18px; font-weight: 700; color: #1A1C1E; margin-bottom: 0px; }
    
    /* Контейнер для KPI */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        height: 140px;
    }
    .kpi-title { font-size: 15px; font-weight: 600; color: #1A1C1E; margin-bottom: 8px; line-height: 1.2; }
    .kpi-value { font-size: 32px; font-weight: 500; color: #6244BB; }
    
    /* Стиль для блоков графиков */
    .bi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    
    /* Убираем лишние отступы у поповеров в карточках */
    div[data-testid="stPopover"] > button {
        border: none;
        padding: 0;
        background: transparent;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def kpi_card(title: str, value: str, help_text: str):
    """Карточка KPI с кнопкой подсказки"""
    st.markdown(f'<div class="kpi-card">', unsafe_allow_html=True)
    cols = st.columns([0.8, 0.2])
    with cols[0]:
        st.markdown(f'<div class="kpi-title">{title}</div>', unsafe_allow_html=True)
    with cols[1]:
        with st.popover("❓"):
            st.caption(help_text)
    st.markdown(f'<div class="kpi-value">{value}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 3) Данные (Логика без изменений)
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
    ttm_stages = ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]
    cycle_stages = ["Бэклог разработки", "В работе"]
    for col in set(ttm_stages + cycle_stages):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["ttm_days"] = df[ttm_stages].sum(axis=1) / 1440
    df["cycle_time"] = df[cycle_stages].sum(axis=1) / 1440
    df["Резолюция"] = df.get("Резолюция", pd.Series(["Не указано"]*len(df))).fillna("Не указано")
    df["Компоненты"] = df.get("Компоненты", pd.Series(["Не указано"]*len(df))).fillna("Не указано")
    df["Приоритет"] = df.get("Приоритет", pd.Series(["Не указано"]*len(df))).fillna("Не указано")
    return df

df = load_data()

if df.empty:
    st.warning("Данные не найдены.")
    st.stop()

# --- САЙДБАР ---
db_min, db_max = df["Дата создания"].min().date(), df["Дата создания"].max().date()
date_range = st.sidebar.date_input("Период анализа", value=(db_max - timedelta(days=7), db_max), min_value=db_min, max_value=db_max)

if not (isinstance(date_range, tuple) and len(date_range) == 2): st.stop()

start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
sel_teams = st.sidebar.multiselect("Команды", sorted(df["Компоненты"].unique()), default=sorted(df["Компоненты"].unique()))
sel_res = st.sidebar.multiselect("Резолюции", sorted(df["Резолюция"].unique()), default=sorted(df["Резолюция"].unique()))

f_df = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d) & 
          (df["Компоненты"].isin(sel_teams)) & (df["Резолюция"].isin(sel_res))].copy()

# --- ЗАГОЛОВОК ---
st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

# --- KPI ---
k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Всего задач", f"{len(f_df)}", "Общее количество задач, созданных за выбранный период.")
with k2:
    ttm = f_df["ttm_days"].mean() if len(f_df) else 0
    kpi_card("TTM (в днях)", f"{ttm:.2f}", "Time to Market: среднее время жизни задачи от создания до финала.")
with k3:
    ct = f_df["cycle_time"].mean() if len(f_df) else 0
    kpi_card("Cycle Time (дн)", f"{ct:.2f}", "Чистое время работы: Бэклог + В работе.")
with k4:
    crit = len(f_df[(f_df["Резолюция"] == "Позже") & (f_df["Приоритет"] == "Критичный")])
    kpi_card("Критичные позже", f"{crit}", "Задачи с приоритетом 'Критичный', выполнение которых было перенесено.")

st.markdown("<br>", unsafe_allow_html=True)

# --- ГРАФИКИ ---
c1, c2 = st.columns(2, gap="large")
t_order = f_df["Компоненты"].value_counts().index.tolist()

with c1:
    st.markdown('<div class="bi-card">', unsafe_allow_html=True)
    header_cols = st.columns([0.9, 0.1])
    header_cols[0].markdown('<div class="card-header">Нагрузка по командам</div>', unsafe_allow_html=True)
    with header_cols[1]:
        with st.popover("❓"): st.write("Распределение количества задач по командам и их статусам готовности.")
    
    t_counts = f_df.groupby(["Компоненты", "Резолюция"]).size().reset_index(name="Кол-во")
    fig_l = px.bar(t_counts, x="Кол-во", y="Компоненты", color="Резолюция", orientation="h", text="Кол-во",
                   category_orders={"Компоненты": t_order}, color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"}, template="plotly_white")
    fig_l.update_layout(height=350, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig_l, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown('<div class="bi-card">', unsafe_allow_html=True)
    header_cols = st.columns([0.9, 0.1])
    header_cols[0].markdown('<div class="card-header">Среднее время работы</div>', unsafe_allow_html=True)
    with header_cols[1]:
        with st.popover("❓"): st.write("Средний TTM в разрезе команд. Помогает найти 'узкие места' в процессах.")
    
    t_avg = f_df.groupby("Компоненты")["ttm_days"].mean().reset_index()
    fig_a = px.bar(t_avg, x="ttm_days", y="Компоненты", orientation="h", text_auto=".1f",
                   color_discrete_sequence=["#6244BB"], template="plotly_white", category_orders={"Компоненты": t_order})
    fig_a.update_layout(height=350, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig_a, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# --- ДИНАМИКА ---
st.markdown('<div class="bi-card">', unsafe_allow_html=True)
dh1, dh_hint, dh2 = st.columns([5, 0.5, 1.5])
with dh1:
    st.markdown('<div class="card-header">Динамика поступления задач</div>', unsafe_allow_html=True)
with dh_hint:
    with st.popover("❓"): st.write("Тренд создания новых тикетов. Позволяет оценить нагрузку на дежурных во времени.")
with dh2:
    unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], label_visibility="collapsed")

u_map = {"День": "D", "Неделя": "W", "Месяц": "ME"}
resampled = f_df.set_index("Дата создания").resample(u_map[unit]).size().reset_index(name="Задач")
fig_d = px.line(resampled, x="Дата создания", y="Задач", markers=True, color_discrete_sequence=["#6244BB"], template="plotly_white")
fig_d.update_layout(height=300, xaxis_title=None, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig_d, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)
