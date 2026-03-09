import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta, date

# 1) Настройка страницы
st.set_page_config(page_title="Аналитика дежурств", layout="wide")

# 2) BI-стиль + тултипы + sidebar chips + календарь (фиолетовый) + русификация поля
st.markdown(
    """
    <style>
    /* ===================== BASE THEME ===================== */
    .stApp { background-color: #F7F2FA; }

    /* ===================== SIDEBAR ===================== */
    [data-testid="stSidebar"] { 
        background: linear-gradient(180deg, #A485E0 0%, #8E6EDB 100%);
        color: white;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {
        color: white !important;
    }

    /* Контейнер select/multiselect: белый, скруглённый */
    [data-baseweb="select"] > div {
        background-color: white !important;
        border-radius: 14px !important;
        border: none !important;
        min-height: 48px !important;
    }

    /* input внутри multiselect */
    [data-baseweb="select"] input { color: #1A1C1E !important; }

    /* chips выбранных элементов */
    [data-baseweb="tag"] {
        background-color: #6244BB !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 2px 6px !important;
        font-size: 13px !important;
    }
    [data-baseweb="tag"] span { color: white !important; font-weight: 500 !important; }
    [data-baseweb="tag"] svg { fill: white !important; }

    /* стрелка dropdown */
    [data-baseweb="select"] svg { fill: #6244BB !important; }

    /* hover/focus обводка */
    [data-baseweb="select"] > div:hover { box-shadow: 0 0 0 1px #6244BB inset !important; }
    [data-baseweb="select"] > div:focus-within { box-shadow: 0 0 0 2px #6244BB inset !important; }

    /* ===================== DATE INPUT (SAFE PURPLE) ===================== */
    /* скрыть английский helper "Choose a date range" */
    [data-testid="stDateInput"] p { display: none !important; }

    /* Красим только выделенные/диапазонные дни по точным классам (не трогаем все кнопки!) */
    .react-datepicker__day--selected,
    .react-datepicker__day--keyboard-selected,
    .react-datepicker__day--range-start,
    .react-datepicker__day--range-end {
        background-color: #6244BB !important;
        color: #ffffff !important;
        border-radius: 999px !important;
    }
    .react-datepicker__day--in-range,
    .react-datepicker__day--in-selecting-range {
        background-color: rgba(98, 68, 187, 0.22) !important;
        color: #1A1C1E !important;
        border-radius: 10px !important;
    }

    .rdp-day_selected,
    .rdp-day_range_start,
    .rdp-day_range_end {
        background-color: #6244BB !important;
        color: #ffffff !important;
    }
    .rdp-day_range_middle {
        background-color: rgba(98, 68, 187, 0.22) !important;
        color: #1A1C1E !important;
    }

    /* Иногда выделение отмечается aria-selected */
    [data-testid="stDateInput"] [aria-selected="true"]{
        background-color: #6244BB !important;
        color: #ffffff !important;
        border-radius: 999px !important;
    }

    /* ===================== LAYOUT ===================== */
    .block-container {
        padding-top: 2.0rem !important;
        padding-bottom: 0.65rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
        max-width: 100% !important;
    }

    div[data-testid="stVerticalBlock"] > div {
        gap: 0.6rem;
    }

    /* Заголовки */
    .main-header { font-size: 32px; font-weight: 800; color: #1A1C1E; margin: 0 0 10px 0; }
    .card-header { font-size: 18px; font-weight: 700; color: #1A1C1E; display: inline-block; }

    /* KPI карточки */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 14px 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        text-align: left;
        height: 110px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .kpi-title {
        font-size: 15px;
        font-weight: 650;
        color: #1A1C1E;
        min-height: 42px;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        line-height: 1.25;
    }
    .kpi-value {
        font-size: 30px;
        font-weight: 600;
        color: #6244BB;
        line-height: 1;
        margin-top: auto;
    }

    /* Иконка подсказки */
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

    /* Тултип */
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

    /* Графики как карточки */
    [data-testid="stPlotlyChart"] {
        background: white;
        border-radius: 6px;
        padding: 6px;
        box-shadow: 0 6px 12px rgba(0,0,0,0.06);
        border: 1px solid #ECEAF3;
        overflow: hidden;
    }

    /* Таблица */
    th {
        background-color: #6244BB !important;
        color: white !important;
        font-weight: 600 !important;
        text-align: left !important;
    }
    thead tr th:first-child { display:none; }
    tbody tr th:first-child { display:none; }
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

    ttm_stages = ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]
    cycle_stages = ["Бэклог разработки", "В работе"]

    for col in set(ttm_stages + cycle_stages):
        if col not in df_.columns:
            df_[col] = 0
        df_[col] = pd.to_numeric(df_[col], errors="coerce").fillna(0)

    df_["ttm_days"] = df_[ttm_stages].sum(axis=1) / 1440
    df_["cycle_time"] = df_[cycle_stages].sum(axis=1) / 1440
    df_["wait_time_days"] = (df_["ttm_days"] - df_["cycle_time"]).clip(lower=0)

    df_["Резолюция"] = df_.get("Резолюция", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Компоненты"] = df_.get("Компоненты", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Приоритет"] = df_.get("Приоритет", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")

    return df_

df = load_data()
if df.empty:
    st.warning("Данные не найдены.")
    st.stop()

# ===================== SIDEBAR FILTERS (FIXED DATE RANGE) =====================
db_min = df["Дата создания"].min().date()
db_max = df["Дата создания"].max().date()

default_start = max(db_min, db_max - timedelta(days=7))
default_range = (default_start, db_max)

st.sidebar.markdown(
    "<div style='font-size:20px; font-weight:600; margin-bottom:-35px;'>Выбор даты</div>",
    unsafe_allow_html=True
)
date_range = st.sidebar.date_input(
    "Период анализа",
    value=st.session_state.get("date_range", default_range),
    min_value=db_min,
    max_value=db_max,
    key="date_range",
    format="DD.MM.YYYY"
)

# Нормализуем значение после выбора
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
elif isinstance(date_range, (date,)):
    start_date, end_date = date_range, date_range
else:
    st.stop()

if start_date > end_date:
    start_date, end_date = end_date, start_date

start_d = pd.to_datetime(start_date)
end_d = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

all_teams = sorted(df["Компоненты"].dropna().unique().tolist())

df_in_range = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d)].copy()
if df_in_range.empty:
    st.sidebar.warning("За выбранный период данных нет.")
    st.stop()

# --- доступные значения в текущем диапазоне ---
teams_in_range = sorted(df_in_range["Компоненты"].dropna().unique().tolist())
res_in_range = sorted(df_in_range["Резолюция"].dropna().unique().tolist())

# --- ключ "сигнатуры" периода, чтобы понять что период изменился ---
period_sig = (start_date, end_date)

# если период поменялся — сбрасываем выбор фильтров на "все доступные"
if st.session_state.get("_period_sig") != period_sig:
    st.session_state["_period_sig"] = period_sig
    st.session_state["sel_teams"] = teams_in_range
    st.session_state["sel_res"] = res_in_range

sel_teams = st.sidebar.multiselect("Команды", teams_in_range, default=st.session_state["sel_teams"], key="sel_teams")
sel_res = st.sidebar.multiselect("Резолюции", res_in_range, default=st.session_state["sel_res"], key="sel_res")

f_df = df_in_range[(df_in_range["Компоненты"].isin(sel_teams)) & (df_in_range["Резолюция"].isin(sel_res))].copy()

# ===================== UI =====================
st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

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

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

c1, c2 = st.columns(2, gap="small")
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
    fig_l.update_layout(height=270, xaxis_title=None, yaxis_title=None, margin=dict(l=50, r=50, t=0, b=0))
    st.plotly_chart(
        fig_l,
        use_container_width=True
    )

with c2:
    st.markdown(
        f'<div class="card-header">Cycle vs ожидание</div>'
        f'<span class="hint-icon" data-hint="Средний Cycle time и среднее ожидание (TTM − Cycle) по командам">?</span>',
        unsafe_allow_html=True
    )

    t_parts = (
        f_df.groupby("Компоненты")[["cycle_time", "wait_time_days"]]
        .mean()
        .reset_index()
    )

    t_parts_long = t_parts.melt(
        id_vars="Компоненты",
        value_vars=["cycle_time", "wait_time_days"],
        var_name="Метрика",
        value_name="Дни"
    )

    name_map = {"cycle_time": "Cycle time", "wait_time_days": "Ожидание"}
    t_parts_long["Метрика"] = t_parts_long["Метрика"].map(name_map)

    fig_a = px.bar(
        t_parts_long,
        x="Дни",
        y="Компоненты",
        color="Метрика",
        orientation="h",
        barmode="stack",
        text_auto=".1f",
        category_orders={"Компоненты": t_order},
        color_discrete_map={"Cycle time": "#6244BB", "Ожидание": "#A485E0"},
        template="plotly_white",
    )
    fig_a.update_layout(
        height=270,
        xaxis_title=None,
        yaxis_title=None,
        legend_title=None,
        margin=dict(l=0, r=0, t=0, b=0),
    )

    st.plotly_chart(fig_a, use_container_width=True)

b1, b2 = st.columns([3, 2], gap="large")

with b1:
    st.markdown(
        f'<div class="card-header">Динамика поступления задач</div>'
        f'<span class="hint-icon" data-hint="Количество новых задач по дням/неделям/месяцам">?</span>',
        unsafe_allow_html=True
    )
    unit = st.selectbox("Групп.", ["День", "Неделя", "Месяц"], key="unit_bottom", label_visibility="collapsed")
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
    fig_d.update_layout(height=170, xaxis_title=None, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_d, use_container_width=True)

with b2:
    st.markdown(
        f'<div class="card-header">Команды без задач</div>'
        f'<span class="hint-icon" data-hint="Команды, у которых не было задач в выбранный период">?</span>',
        unsafe_allow_html=True
    )
    active_teams_in_period = df_in_range["Компоненты"].dropna().unique()
    inactive_teams = sorted([team for team in all_teams if team not in active_teams_in_period])

    if inactive_teams:
        inactive_df = pd.DataFrame(inactive_teams, columns=["Команда"])
        st.dataframe(inactive_df, use_container_width=True, height=170, hide_index=True)
    else:
        st.success("Все команды были активны в этот период.")
