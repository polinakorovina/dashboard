import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta, datetime

# 1) Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2) BI-стиль + Исправленный CSS для календаря
st.markdown(
    """
    <style>
    .stApp { background-color: #F7F2FA; }

    /* САЙДБАР: Красим только заголовки и текст, не трогая внутренности инпутов */
    [data-testid="stSidebar"] { background-color: #A485E0; }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color: white !important; font-weight: 600; }
    [data-testid="stSidebar"] .stMarkdown p { color: white !important; }
    
    /* Исправляем видимость текста в календаре */
    [data-testid="stSidebar"] div[data-baseweb="input"] input {
        color: #1A1C1E !important; /* Текст внутри календаря снова темный */
        -webkit-text-fill-color: #1A1C1E !important;
    }

    .main-header { font-size: 34px; font-weight: 800; color: #1A1C1E; margin: 4px 0 18px 0; }
    .card-header { font-size: 18px; font-weight: 700; color: #1A1C1E; display: inline-block; margin-bottom: 10px; }

    .kpi-card { background: #ffffff; border: 1px solid #E6E9EF; border-radius: 16px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .kpi-title { font-size: 16px; font-weight: 600; color: #1A1C1E; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
    .kpi-value { font-size: 36px; font-weight: 500; color: #6244BB; line-height: 1.2; }
    
    .bi-card { background: #ffffff; border: 1px solid #E6E9EF; border-radius: 16px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px; }

    /* Таблица: Фиолетовый заголовок и скрытие индекса */
    th { background-color: #6244BB !important; color: white !important; text-align: left !important; }
    thead tr th:first-child, tbody tr th:first-child { display:none; }
    
    .block-container { padding-top: 1.7rem !important; }
    </style>
    """,
    unsafe_allow_html=True
)

def kpi_card(title: str, value: str, hint: str = ""):
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">{title}</div><div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)

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
    df["Дата создания"] = pd.to_datetime(df["Дата создания"], errors="coerce")
    df = df.dropna(subset=["Дата создания"])
    # Расчет TTM и других полей (сокращено для примера)
    stages = ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]
    for col in stages: df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
    df["ttm_days"] = df[stages].sum(axis=1) / 1440
    df["cycle_time"] = df[["Бэклог разработки", "В работе"]].sum(axis=1) / 1440
    return df

df = load_data()
if df.empty: st.stop()

# --- ЛОГИКА КАЛЕНДАРЯ ОТ ДАТЫ В ДАННЫХ ---
db_max = df["Дата создания"].max().date()
db_min = df["Дата создания"].min().date()

st.sidebar.markdown("### Быстрые фильтры")
col_b1, col_b2 = st.sidebar.columns(2)

# Кнопки сброса к периодам от MAX даты данных
if col_b1.button("Последние 7 дней"):
    st.session_state.d_range = (db_max - timedelta(days=7), db_max)
if col_b2.button("Последние 30 дней"):
    st.session_state.d_range = (db_max - timedelta(days=30), db_max)
if st.sidebar.button("Весь период"):
    st.session_state.d_range = (db_min, db_max)

# Инициализация значения в session_state, если его еще нет
if 'd_range' not in st.session_state:
    st.session_state.d_range = (db_max - timedelta(days=7), db_max)

# Календарь
date_range = st.sidebar.date_input(
    "Период анализа", 
    value=st.session_state.d_range,
    min_value=db_min,
    max_value=db_max,
    key="calendar_input" # используем ключ, но session_state выше приоритетнее
)

# Синхронизируем выбор пользователя обратно в session_state
if isinstance(date_range, tuple) and len(date_range) == 2:
    st.session_state.d_range = date_range
    start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
else:
    st.stop()

# Остальные фильтры
all_teams = sorted(df["Компоненты"].unique().tolist())
sel_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams)
sel_res = st.sidebar.multiselect("Резолюции", sorted(df["Резолюция"].unique().tolist()), default=sorted(df["Резолюция"].unique().tolist()))

# --- ФИЛЬТРАЦИЯ И ВЫВОД ---
f_df = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d) & 
          (df["Компоненты"].isin(sel_teams)) & (df["Резолюция"].isin(sel_res))].copy()

st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

# (Далее идет код KPI, графиков и таблицы без изменений...)
# ... [ТВОЙ КОД KPI И ГРАФИКОВ] ...

# Код таблицы (для примера)
df_period_res = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d) & (df["Резолюция"].isin(sel_res))]
active_teams_in_period = df_period_res["Компоненты"].unique()
inactive_teams = sorted([team for team in all_teams if team not in active_teams_in_period])

st.markdown('<div class="bi-card">', unsafe_allow_html=True)
if inactive_teams:
    inactive_df = pd.DataFrame(inactive_teams, columns=["Команды без задач за анализируемый период"])
    st.table(inactive_df)
else:
    st.success("Все команды активны.")
st.markdown("</div>", unsafe_allow_html=True)
