import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta

# 1) Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2) Стилизация: Фиолетовый фон и единые белые плашки
st.markdown(
    """
    <style>
    /* Фон всей страницы */
    .stApp { background-color: #F7F2FA; }

    /* Сайдбар */
    [data-testid="stSidebar"] { background-color: #A485E0; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }

    /* Основная белая плашка (для KPI и Графиков) */
    .bi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        height: 100%;
    }

    /* Заголовок внутри плашки */
    .card-header { 
        font-size: 18px; 
        font-weight: 700; 
        color: #1A1C1E; 
        display: flex;
        align-items: center;
    }

    /* Круглая серая иконка подсказки */
    .hint-icon {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        width: 18px;
        height: 18px;
        background-color: #E6E9EF;
        color: #7E8694;
        border-radius: 50%;
        font-size: 11px;
        font-weight: bold;
        cursor: help;
        margin-left: 8px;
        position: relative;
    }

    /* Тултип при наведении */
    .hint-icon:hover::after {
        content: attr(data-hint);
        position: absolute;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        background-color: #1A1C1E;
        color: #fff;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 12px;
        width: 200px;
        z-index: 1000;
        font-weight: normal;
        line-height: 1.4;
    }

    /* KPI стили */
    .kpi-value { font-size: 36px; font-weight: 500; color: #6244BB; line-height: 1.2; margin-top: 10px; }
    
    /* Убираем лишние отступы колонок */
    [data-testid="column"] { padding: 0px 10px !important; }
    .block-container { padding-top: 2rem !important; }
    
    /* Скрытие стандартных рамок Plotly */
    .js-plotly-plot { margin-top: 10px; }
    </style>
    """,
    unsafe_allow_html=True
)

# Функция для отрисовки KPI (уже на плашке)
def draw_kpi(title, value, hint):
    st.markdown(f"""
        <div class="bi-card">
            <div class="card-header">
                {title} <span class="hint-icon" data-hint="{hint}">?</span>
            </div>
            <div class="kpi-value">{value}</div>
        </div>
    """, unsafe_allow_html=True)

# 3) Логика данных
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
    for col in stages:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
    
    df["ttm_days"] = df[stages].sum(axis=1) / 1440
    df["cycle_time"] = df[["Бэклог разработки", "В работе"]].sum(axis=1) / 1440
    df["Резолюция"] = df.get("Резолюция", "Не указано").fillna("Не указано")
    df["Компоненты"] = df.get("Компоненты", "Не указано").fillna("Не указано")
    df["Приоритет"] = df.get("Приоритет", "Средний").fillna("Средний")
    return df

df = load_data()

if df.empty:
    st.warning("Данные не загружены.")
    st.stop()

# --- ФИЛЬТРЫ (Сайдбар) ---
db_min, db_max = df["Дата создания"].min().date(), df["Дата создания"].max().date()
date_range = st.sidebar.date_input("Период", value=(db_max - timedelta(days=7), db_max))
sel_teams = st.sidebar.multiselect("Команды", sorted(df["Компоненты"].unique()), default=sorted(df["Компоненты"].unique()))

if len(date_range) == 2:
    f_df = df[(df["Дата создания"].dt.date >= date_range[0]) & 
              (df["Дата создания"].dt.date <= date_range[1]) & 
              (df["Компоненты"].isin(sel_teams))].copy()
else:
    st.stop()

# --- КОНТЕНТ ---
st.markdown('<h1 style="color: #1A1C1E; font-weight: 800; margin-bottom: 25px;">Аналитика дежурств</h1>', unsafe_allow_html=True)

# Секция KPI
k1, k2, k3, k4 = st.columns(4)
with k1: draw_kpi("Всего задач", str(len(f_df)), "Общее количество тикетов за период")
with k2: draw_kpi("TTM в днях", f"{f_df['ttm_days'].mean():.2f}", "Среднее время от создания до закрытия")
with k3: draw_kpi("Cycle time (дн)", f"{f_df['cycle_time'].mean():.2f}", "Время нахождения в статусах разработки")
with k4: 
    crit = len(f_df[(f_df["Резолюция"] == "Позже") & (f_df["Приоритет"] == "Критичный")])
    draw_kpi("Критичные позже", str(crit), "Криты, которые были отложены")

st.write("") 

# Секция графиков (Нагрузка и Среднее время)
c1, c2 = st.columns(2)
t_order = f_df["Компоненты"].value_counts().index.tolist()

with c1:
    st.markdown(f"""
        <div class="bi-card">
            <div class="card-header">
                Нагрузка по командам <span class="hint-icon" data-hint="Количество задач в разрезе команд и их резолюции">?</span>
            </div>
    """, unsafe_allow_html=True)
    t_counts = f_df.groupby(["Компоненты", "Резолюция"]).size().reset_index(name="Кол-во")
    fig_l = px.bar(t_counts, x="Кол-во", y="Компоненты", color="Резолюция", orientation="h", text="Кол-во",
                   category_orders={"Компоненты": t_order}, color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"}, template="plotly_white")
    fig_l.update_layout(height=350, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=10, t=10, b=0), showlegend=True)
    st.plotly_chart(fig_l, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown(f"""
        <div class="bi-card">
            <div class="card-header">
                Среднее время работы <span class="hint-icon" data-hint="Средний TTM в днях для каждой команды">?</span>
            </div>
    """, unsafe_allow_html=True)
    t_avg = f_df.groupby("Компоненты")["ttm_days"].mean().reset_index()
    fig_a = px.bar(t_avg, x="ttm_days", y="Компоненты", orientation="h", text_auto=".1f",
                   color_discrete_sequence=["#6244BB"], template="plotly_white", category_orders={"Компоненты": t_order})
    fig_a.update_layout(height=350, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig_a, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Секция динамики
st.markdown(f"""
    <div class="bi-card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
            <div class="card-header">
                Динамика поступления задач <span class="hint-icon" data-hint="Тренд создания новых задач">?</span>
            </div>
    """, unsafe_allow_html=True)

# Выбор группировки внутри той же плашки
unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], label_visibility="collapsed")
u_map = {"День": "D", "Неделя": "W", "Месяц": "ME"}
resampled = f_df.set_index("Дата создания").resample(u_map[unit]).size().reset_index(name="Задач")

fig_d = px.line(resampled, x="Дата создания", y="Задач", markers=True, color_discrete_sequence=["#6244BB"], template="plotly_white")
fig_d.update_layout(height=300, xaxis_title=None, margin=dict(l=0, r=0, t=20, b=0))
st.plotly_chart(fig_d, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)
