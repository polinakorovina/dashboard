import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta

# 1) Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2) BI-стиль (стабильный, без ломания верстки)
st.markdown(
    """
    <style>
    /* Общий фон */
    .stApp { background-color: #F8F9FB; }

    /* Сайдбар */
    [data-testid="stSidebar"] { background-color: #A485E0; color: white; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {
        color: white !important;
    }

    /* Заголовки */
    .main-header {
        font-size: 34px;
        font-weight: 800;
        color: #1A1C1E;
        margin: 4px 0 18px 0;
    }

    .card-header {
        font-size: 18px;
        font-weight: 700;
        color: #1A1C1E;
        margin-bottom: 14px;
    }

    /* Карточки для графиков */
    .bi-card {
        background-color: white;
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
        border: 1px solid #E6E9EF;
        margin-bottom: 24px;
    }

    /* KPI карточки (как BI, но адаптивно и без конфликтов) */
    .kpi-card{
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        text-align: left;
        width: 100%;
    }

    .kpi-title{
        font-size: 18px;
        font-weight: 600;
        color: #1A1C1E;
        margin-bottom: 12px;
        white-space: nowrap; /* не переносить по буквам */
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .kpi-value{
        font-size: 36px;
        font-weight: 500;
        color: #6244BB;
        line-height: 1.2;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def kpi_card(title: str, value: str):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# 3) Подключение к Я.Диску + БД
TOKEN = os.getenv("YANDEX_TOKEN")
y = yadisk.YaDisk(token=TOKEN)
DB_PATH = "/Data/my_database.db"

@st.cache_data(ttl=600)
def load_data():
    if not y.exists(DB_PATH):
        return pd.DataFrame()

    y.download(DB_PATH, "local_view.db")
    conn = sqlite3.connect("local_view.db")
    df = pd.read_sql("SELECT * FROM tasks", conn)
    conn.close()

    # Дата создания обязательна
    if "Дата создания" not in df.columns:
        return pd.DataFrame()

    df["Дата создания"] = pd.to_datetime(df["Дата создания"], errors="coerce")
    df = df.dropna(subset=["Дата создания"])

    # Статусы в минутах (если нет — создадим)
    ttm_stages = ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]
    cycle_stages = ["Бэклог разработки", "В работе"]

    for col in set(ttm_stages + cycle_stages):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0

    # Метрики: минуты -> дни
    df["ttm_days"] = df[ttm_stages].sum(axis=1) / 1440
    df["cycle_time"] = df[cycle_stages].sum(axis=1) / 1440

    # Заполнения текстовых полей
    if "Резолюция" in df.columns:
        df["Резолюция"] = df["Резолюция"].fillna("Не указано")
    else:
        df["Резолюция"] = "Не указано"

    if "Компоненты" not in df.columns:
        df["Компоненты"] = "Не указано"

    if "Приоритет" in df.columns:
        df["Приоритет"] = df["Приоритет"].fillna("Не указано")
    else:
        df["Приоритет"] = "Не указано"

    return df

df = load_data()

if df.empty:
    st.warning("Данные не найдены или таблица пустая.")
    st.stop()

# --- САЙДБАР ---
st.sidebar.header("Настройки фильтров")

db_min = df["Дата создания"].min().date()
db_max = df["Дата создания"].max().date()

date_range = st.sidebar.date_input(
    "Период анализа",
    value=(db_max - timedelta(days=7), db_max),
    min_value=db_min,
    max_value=db_max
)

if not (isinstance(date_range, tuple) and len(date_range) == 2):
    st.stop()

start_d = pd.to_datetime(date_range[0])
end_d = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

all_teams = sorted(df["Компоненты"].dropna().unique().tolist())
sel_teams = st.sidebar.multiselect("Команды", all_teams, default=all_teams)

all_res = sorted(df["Резолюция"].dropna().unique().tolist())
sel_res = st.sidebar.multiselect("Резолюции", all_res, default=all_res)

f_df = df[
    (df["Дата создания"] >= start_d) &
    (df["Дата создания"] <= end_d) &
    (df["Компоненты"].isin(sel_teams)) &
    (df["Резолюция"].isin(sel_res))
].copy()

# --- ЗАГОЛОВОК ---
st.markdown('<div class="main-header">📊 Аналитика дежурств</div>', unsafe_allow_html=True)

# --- KPI ---
k1, k2, k3, k4 = st.columns(4, gap="medium")

ttm_mean = float(f_df["ttm_days"].mean()) if len(f_df) else 0.0
cycle_mean = float(f_df["cycle_time"].mean()) if len(f_df) else 0.0
crit_late = len(f_df[(f_df["Резолюция"] == "Позже") & (f_df["Приоритет"] == "Критичный")])
total_tasks = len(f_df)

with k1:
    kpi_card("TTM (средний)", f"{ttm_mean:.2f}".replace(",", "."))
with k2:
    kpi_card("cycle time", f"{cycle_mean:.2f}".replace(",", "."))
with k3:
    kpi_card("Критичные 'Позже'", f"{crit_late}")
with k4:
    kpi_card("Всего задач", f"{total_tasks}")

st.markdown("<br>", unsafe_allow_html=True)

# --- ГРАФИКИ ---
c1, c2 = st.columns(2, gap="large")

# порядок команд
t_order = f_df["Компоненты"].value_counts().index.tolist()

with c1:
    st.markdown('<div class="bi-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header">Нагрузка по командам</div>', unsafe_allow_html=True)

    t_counts = f_df.groupby(["Компоненты", "Резолюция"]).size().reset_index(name="Кол-во")

    fig_l = px.bar(
        t_counts,
        x="Кол-во",
        y="Компоненты",
        color="Резолюция",
        orientation="h",
        text="Кол-во",
        category_orders={"Компоненты": t_order},
        color_discrete_map={"Решен": "#6244BB", "Позже": "#A485E0"},
        template="plotly_white"
    )
    fig_l.update_traces(textposition="outside")
    fig_l.update_layout(height=400, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=40, t=0, b=0))
    st.plotly_chart(fig_l, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown('<div class="bi-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header">Среднее время работы (TTM)</div>', unsafe_allow_html=True)

    t_avg = f_df.groupby("Компоненты")["ttm_days"].mean().reset_index()
    t_avg["Компоненты"] = pd.Categorical(t_avg["Компоненты"], categories=t_order, ordered=True)
    t_avg = t_avg.sort_values("Компоненты", ascending=False)

    fig_a = px.bar(
        t_avg,
        x="ttm_days",
        y="Компоненты",
        orientation="h",
        text_auto=".1f",
        color_discrete_sequence=["#6244BB"],
        template="plotly_white"
    )
    fig_a.update_traces(textposition="outside")
    fig_a.update_layout(height=400, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=40, t=0, b=0))
    st.plotly_chart(fig_a, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# --- ДИНАМИКА ---
st.markdown('<div class="bi-card">', unsafe_allow_html=True)
dh1, dh2 = st.columns([5, 1])

with dh1:
    st.markdown('<div class="card-header">📈 Динамика поступления</div>', unsafe_allow_html=True)
with dh2:
    unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], label_visibility="collapsed")

u_map = {"День": "D", "Неделя": "W", "Месяц": "ME"}

resampled = f_df.set_index("Дата создания").resample(u_map[unit]).size().reset_index(name="Задач")

fig_d = px.line(
    resampled,
    x="Дата создания",
    y="Задач",
    markers=True,
    color_discrete_sequence=["#6244BB"],
    template="plotly_white"
)
fig_d.update_layout(height=300, xaxis_title=None, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig_d, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)
