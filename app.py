import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta

# 1) Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2) BI-стиль + Кастомные тултипы
st.markdown(
    """
    <style>
    /* Общий фон */
    .stApp { background-color: #F7F2FA; }

    /* Сайдбар */
    [data-testid="stSidebar"] { background-color: #A485E0; color: white; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
        color: white !important;
    }

    /* Заголовки */
    .main-header { font-size: 34px; font-weight: 800; color: #1A1C1E; margin: 4px 0 18px 0; }
    .card-header { font-size: 18px; font-weight: 700; color: #1A1C1E; display: inline-block; }

    /* KPI карточки */
    .kpi-card {
    background: #ffffff;
    border: 1px solid #E6E9EF;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    text-align: left;
    height: 110px;              /* фиксированная высота карточки */
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    }
    
    .kpi-title {
        font-size: 16px;
        font-weight: 600;
        color: #1A1C1E;
        min-height: 30px;           /* одинаковая высота под заголовок */
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        line-height: 1.35;
    }
    
    .kpi-value {
        font-size: 36px;
        font-weight: 500;
        color: #6244BB;
        line-height: 1;
        margin-top: auto;
    }
    /* КРУГЛАЯ СЕРАЯ ИКОНКА ПОДСКАЗКИ */
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
        flex: 0 0 auto;
    }

    /* Тултип (текст при наведении) */
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
        width: 220px;
        white-space: normal;
        z-index: 1000;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        font-weight: normal;
    }

    /* СТИЛИЗАЦИЯ ТАБЛИЦЫ */
    th {
        background-color: #6244BB !important;
        color: white !important;
        font-weight: 600 !important;
        text-align: left !important;
    }
    /* СКРЫТИЕ ИНДЕКСОВ в st.table */
    thead tr th:first-child { display:none; }
    tbody tr th:first-child { display:none; }

    .block-container { padding-top: 1.7rem !important; }
    </style>
    """,
    unsafe_allow_html=True
)

def kpi_card(title: str, value: str, hint: str = ""):
    hint_html = f'<span class="hint-icon" data-hint="{hint}">?</span>' if hint else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title} {hint_html}</div>
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
    df_ = pd.read_sql("SELECT * FROM tasks", conn)
    conn.close()

    if "Дата создания" not in df_.columns:
        return pd.DataFrame()

    df_["Дата создания"] = pd.to_datetime(df_["Дата создания"], errors="coerce")
    df_ = df_.dropna(subset=["Дата создания"])

    # Стадии
    ttm_stages = ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]
    cycle_stages = ["Бэклог разработки", "В работе"]

    for col in set(ttm_stages + cycle_stages):
        if col not in df_.columns:
            df_[col] = 0
        df_[col] = pd.to_numeric(df_[col], errors="coerce").fillna(0)

    # Метрики (в днях)
    df_["ttm_days"] = df_[ttm_stages].sum(axis=1) / 1440
    df_["cycle_time"] = df_[cycle_stages].sum(axis=1) / 1440

    # Ожидание (вне активной работы)
    df_["wait_time_days"] = (df_["ttm_days"] - df_["cycle_time"]).clip(lower=0)

    # Текстовые поля
    df_["Резолюция"] = df_.get("Резолюция", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Компоненты"] = df_.get("Компоненты", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Приоритет"] = df_.get("Приоритет", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")

    return df_

df = load_data()

if df.empty:
    st.warning("Данные не найдены.")
    st.stop()

# --- САЙДБАР: диапазон дат и "живые" фильтры ---
db_min = df["Дата создания"].min().date()
db_max = df["Дата создания"].max().date()
default_range = (db_max - timedelta(days=7), db_max)

# ВАЖНО: date_input с key берёт значение из session_state => нужно "обрезать" ДО отрисовки
saved = st.session_state.get("date_range", default_range)
if not (isinstance(saved, tuple) and len(saved) == 2):
    saved = default_range

s0, s1 = saved
s0 = pd.to_datetime(s0).date()
s1 = pd.to_datetime(s1).date()

s0 = max(db_min, min(s0, db_max))
s1 = max(db_min, min(s1, db_max))
if s0 > s1:
    s0, s1 = s1, s0

st.session_state["date_range"] = (s0, s1)

date_range = st.sidebar.date_input(
    "Период анализа",
    min_value=db_min,
    max_value=db_max,
    key="date_range"
)

if not (isinstance(date_range, tuple) and len(date_range) == 2):
    st.stop()

start_d = pd.to_datetime(date_range[0])
end_d = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

# Все команды в базе (нужно для таблицы "без задач")
all_teams = sorted(df["Компоненты"].dropna().unique().tolist())

# Сначала фильтруем по датам
df_in_range = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d)].copy()
if df_in_range.empty:
    st.sidebar.warning("За выбранный период данных нет.")
    st.stop()

# Команды/резолюции — только те, что реально были в период
teams_in_range = sorted(df_in_range["Компоненты"].dropna().unique().tolist())
res_in_range = sorted(df_in_range["Резолюция"].dropna().unique().tolist())

# Пересечение прошлого выбора с текущим периодом
prev_teams = st.session_state.get("sel_teams", teams_in_range)
default_teams = [t for t in prev_teams if t in teams_in_range] or teams_in_range

sel_teams = st.sidebar.multiselect(
    "Команды",
    teams_in_range,
    default=default_teams,
    key="sel_teams"
)

prev_res = st.session_state.get("sel_res", res_in_range)
default_res = [r for r in prev_res if r in res_in_range] or res_in_range

sel_res = st.sidebar.multiselect(
    "Резолюции",
    res_in_range,
    default=default_res,
    key="sel_res"
)

# Финальный df
f_df = df_in_range[
    (df_in_range["Компоненты"].isin(sel_teams)) &
    (df_in_range["Резолюция"].isin(sel_res))
].copy()

# --- ЗАГОЛОВОК ---
st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

# --- KPI (5 карточек в один ряд, ожидание = 5-я) ---
k1, k2, k3, k4, k5 = st.columns(5, gap="small")

with k1:
    kpi_card("Всего задач", f"{len(f_df)}", "Общее число задач за период")

with k2:
    val = f_df["ttm_days"].mean() if len(f_df) else 0.0
    kpi_card("TTM в днях", f"{val:.2f}", "Среднее время от открытия до закрытия")

with k3:
    val = f_df["cycle_time"].mean() if len(f_df) else 0.0
    kpi_card("Cycle time (дн)", f"{val:.2f}", "Среднее время активной работы")

with k4:
    crit_late = len(f_df[(f_df["Резолюция"] == "Позже") & (f_df["Приоритет"] == "Критичный")])
    kpi_card("Критичные позже", f"{crit_late}", "Критичные задачи со статусом Позже")

with k5:
    val = f_df["wait_time_days"].mean() if len(f_df) else 0.0
    kpi_card("Ожидание (дн)", f"{val:.2f}", "Среднее время вне активной работы: TTM − Cycle time")

st.markdown("<br>", unsafe_allow_html=True)

# --- ГРАФИКИ (цвета как было) ---
c1, c2 = st.columns(2, gap="large")
t_order = f_df["Компоненты"].value_counts().index.tolist()

with c1:
    st.markdown(
        f'<div class="card-header">Нагрузка по командам</div>'
        f'<span class="hint-icon" data-hint="Количество задач по статусам для каждой команды">?</span>',
        unsafe_allow_html=True
    )
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
    fig_l.update_layout(height=300, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig_l, use_container_width=True)

with c2:
    st.markdown(
        f'<div class="card-header">Среднее время работы</div>'
        f'<span class="hint-icon" data-hint="Средний TTM в днях для каждой команды">?</span>',
        unsafe_allow_html=True
    )
    t_avg = f_df.groupby("Компоненты")["ttm_days"].mean().reset_index()
    fig_a = px.bar(
        t_avg,
        x="ttm_days",
        y="Компоненты",
        orientation="h",
        text_auto=".1f",
        color_discrete_sequence=["#6244BB"],
        template="plotly_white",
        category_orders={"Компоненты": t_order}
    )
    fig_a.update_layout(height=300, xaxis_title=None, yaxis_title=None, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig_a, use_container_width=True)

# --- ДИНАМИКА (цвет как было) ---
dh1, dh2 = st.columns([5, 1])
with dh1:
    st.markdown(
        f'<div class="card-header">Динамика поступления задач</div>'
        f'<span class="hint-icon" data-hint="Количество новых задач по дням/неделям">?</span>',
        unsafe_allow_html=True
    )
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

# --- ТАБЛИЦА: команды без задач за период ---
active_teams_in_period = df_in_range["Компоненты"].dropna().unique()
inactive_teams = sorted([team for team in all_teams if team not in active_teams_in_period])

if inactive_teams:
    inactive_df = pd.DataFrame(inactive_teams, columns=["Команды без задач за анализируемый период"])
    st.table(inactive_df)
else:
    st.success("Все команды были активны в этот период.")
