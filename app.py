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

    header[data-testid="stHeader"] {
        background: #F7F2FA !important;
        height: 1.6rem !important;
        min-height: 1.6rem !important;
    }

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
    [data-testid="stDateInput"] p { display: none !important; }

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

    [data-testid="stDateInput"] [aria-selected="true"]{
        background-color: #6244BB !important;
        color: #ffffff !important;
        border-radius: 999px !important;
    }

    /* ===================== LAYOUT ===================== */
    .block-container {
        padding-top: 0.55rem !important;
        padding-bottom: 0.45rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        max-width: 100% !important;
    }

    div[data-testid="stVerticalBlock"] > div {
        gap: 0.6rem;
    }

    /* Заголовки */
    .main-header { font-size: 24px; font-weight: 800; color: #1A1C1E; margin: 0 0 10px 0; }
    .card-header { font-size: 14px; font-weight: 700; color: #1A1C1E; display: inline-block; }

    /* KPI карточки */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 14px 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        text-align: left;
        height: 100px;
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
        border-radius: 18px;
        padding: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
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


    /* ===================== TABS STYLING ===================== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        margin-bottom: 5px;
    }
    
    .stTabs [data-baseweb="tab"] {
        min-height: 28px !important;
        height: 28px !important;
        min-width: 90px !important;
        padding: 0px 10px !important;
    
        background: #F3EEFC;
        border-radius: 8px;
        color: #5D4AA8;
        border: 1px solid #E4DDF7;
    
        font-size: 12px;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #6244BB !important;
        border: 1px solid #D8CDF4 !important;
        box-shadow: 0 1px 4px rgba(98, 68, 187, 0.06);
    }
    
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* ===================== COMPACT SEGMENT SWITCH ===================== */
    div[role="radiogroup"] {
        gap: 1px !important;
        flex-wrap: nowrap !important;
    }
    
    div[role="radiogroup"] label {
        background: #F3EEFC !important;
        border: 1px solid #E4DDF7 !important;
        border-radius: 8px !important;
        padding: 0px 6px !important;
        min-height: 26px !important;
        display: flex !important;
        align-items: center !important;
    }
    
    /* скрыть кружок radio */
    div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    
    /* текст */
    div[role="radiogroup"] label p {
        font-size: 11px !important;
        font-weight: 700 !important;
        color: #5D4AA8 !important;
        margin: 0 !important;
    }
    
    /* активный вариант */
    div[role="radiogroup"] label:has(input:checked) {
        background: white !important;
        border: 1px solid #D8CDF4 !important;
        box-shadow: 0 1px 4px rgba(98, 68, 187, 0.06);
    }
    
    /* убрать белое выделение текста */
    div[role="radiogroup"] * {
        user-select: none !important;
    }

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


def delta_text(curr, prev, is_percent=False, digits=2):
    if pd.isna(curr) or pd.isna(prev):
        return "н/д"
    diff = curr - prev
    sign = "+" if diff > 0 else ""
    if is_percent:
        return f"{sign}{diff:.1f} п.п."
    return f"{sign}{diff:.{digits}f}"


def format_value(val, is_percent=False, digits=2, as_int=False):
    if pd.isna(val):
        return "н/д"
    if as_int:
        return f"{int(round(val))}"
    if is_percent:
        return f"{val:.1f}%"
    return f"{val:.{digits}f}"


def kpi_compare_card(title, current, previous, hint="", is_percent=False, as_int=False, digits=2):
    current_str = format_value(current, is_percent=is_percent, digits=digits, as_int=as_int)
    previous_str = format_value(previous, is_percent=is_percent, digits=digits, as_int=as_int)
    diff_str = delta_text(current, previous, is_percent=is_percent, digits=digits)
    hint_html = f'<span class="hint-icon" data-hint="{hint}">?</span>' if hint else ""

    st.markdown(
        f"""
        <div class="kpi-card" style="height: 100px; padding: 6px 10px;">
            <div class="kpi-title" style="font-size:12px; min-height:22px;">
                {title} {hint_html}
            </div>
            <div class="kpi-value" style="font-size:20px; line-height:1;">
                {current_str}
            </div>
            <div style="font-size:11px; color:#7E8694; margin-top:2px; line-height:1;">
                Пред. неделя: {previous_str}
            </div>
            <div style="font-size:11px; font-weight:700; color:#4F46E5; margin-top:2px; line-height:1;">
                Изменение: {diff_str}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def get_week_bounds(anchor_date):
    anchor_date = pd.Timestamp(anchor_date).normalize()
    current_week_start = anchor_date - pd.Timedelta(days=anchor_date.weekday())
    current_week_end = current_week_start + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59)

    prev_week_start = current_week_start - pd.Timedelta(days=7)
    prev_week_end = current_week_start - pd.Timedelta(seconds=1)

    return current_week_start, current_week_end, prev_week_start, prev_week_end


def calc_metrics(df_):
    if df_.empty:
        return {
            "tasks_total": 0,
            "ttm": 0.0,
            "cycle": 0.0,
            "wait": 0.0,
            "later_pct": 0.0,
            "active_pct": 0.0,
            "pingpong": 0.0
        }

    ttm_mean = df_["ttm_days"].mean() if "ttm_days" in df_.columns else 0.0
    cycle_mean = df_["cycle_time"].mean() if "cycle_time" in df_.columns else 0.0
    wait_mean = df_["wait_time_days"].mean() if "wait_time_days" in df_.columns else 0.0
    later_pct = (df_["Резолюция"] == "Позже").mean() * 100 if "Резолюция" in df_.columns else 0.0
    active_pct = (cycle_mean / ttm_mean * 100) if ttm_mean > 0 else 0.0
    pingpong_mean = df_["Пинг-понг обращения"].mean() if "Пинг-понг обращения" in df_.columns else 0.0

    return {
        "tasks_total": len(df_),
        "ttm": ttm_mean,
        "cycle": cycle_mean,
        "wait": wait_mean,
        "later_pct": later_pct,
        "active_pct": active_pct,
        "pingpong": pingpong_mean
    }


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
    df_["Пинг-понг обращения"] = pd.to_numeric(df_.get("Пинг-понг обращения", 0), errors="coerce").fillna(1)
    df_["Количество обращений"] = df_.get("Количество обращений", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")

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

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
elif isinstance(date_range, date):
    start_date, end_date = date_range, date_range
else:
    st.stop()

if start_date > end_date:
    start_date, end_date = end_date, start_date

start_d = pd.to_datetime(start_date)
end_d = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

df_in_range = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d)].copy()
if df_in_range.empty:
    st.sidebar.warning("За выбранный период данных нет.")
    st.stop()

teams_in_range = sorted(df_in_range["Компоненты"].dropna().unique().tolist())
res_in_range = sorted(df_in_range["Резолюция"].dropna().unique().tolist())

period_sig = (start_date, end_date)

if st.session_state.get("_period_sig") != period_sig:
    st.session_state["_period_sig"] = period_sig
    st.session_state["sel_teams"] = teams_in_range
    st.session_state["sel_res"] = res_in_range

sel_teams = st.sidebar.multiselect("Команды", teams_in_range, default=st.session_state.get("sel_teams", teams_in_range), key="sel_teams")
sel_res = st.sidebar.multiselect("Резолюции", res_in_range, default=st.session_state.get("sel_res", res_in_range), key="sel_res")

f_df = df_in_range[
    (df_in_range["Компоненты"].isin(sel_teams)) &
    (df_in_range["Резолюция"].isin(sel_res))
].copy()

# ===================== WEEKLY COMPARISON DATA =====================
base_week_df = df[
    (df["Компоненты"].isin(sel_teams)) &
    (df["Резолюция"].isin(sel_res))
].copy()

weekly_ready = False

if not base_week_df.empty:
    anchor_date = base_week_df["Дата создания"].max()
    cw_start, cw_end, pw_start, pw_end = get_week_bounds(anchor_date)

    current_week_df = base_week_df[
        (base_week_df["Дата создания"] >= cw_start) &
        (base_week_df["Дата создания"] <= cw_end)
    ].copy()

    previous_week_df = base_week_df[
        (base_week_df["Дата создания"] >= pw_start) &
        (base_week_df["Дата создания"] <= pw_end)
    ].copy()

    current_metrics = calc_metrics(current_week_df)
    previous_metrics = calc_metrics(previous_week_df)

    weekly_ready = (len(current_week_df) > 0) and (len(previous_week_df) > 0)
else:
    cw_start = cw_end = pw_start = pw_end = pd.Timestamp.today()
    current_week_df = pd.DataFrame()
    previous_week_df = pd.DataFrame()
    current_metrics = calc_metrics(current_week_df)
    previous_metrics = calc_metrics(previous_week_df)

# ===================== UI =====================
st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Общий обзор", "Сравнение недель"])

# =========================================================
# TAB 1 — ОБЩИЙ ОБЗОР
# =========================================================
with tab1:
    k1, k2, k3, k4, k5, k6 = st.columns(6, gap="small")

    with k1:
        kpi_card("Всего задач", f"{len(f_df)}", "Общее число задач за период")
    with k2:
        val = f_df["ttm_days"].mean() if len(f_df) else 0.0
        kpi_card("TTM в днях", f"{val:.2f}", "Среднее время от открытия до закрытия")
    with k3:
        val = f_df["cycle_time"].mean() if len(f_df) else 0.0
        kpi_card("Cycle time (дн)", f"{val:.2f}", "Среднее время активной работы")
    with k4:
        val = f_df["wait_time_days"].mean() if len(f_df) else 0.0
        kpi_card("Ожидание (дн)", f"{val:.2f}", "Среднее время вне активной работы: TTM − Cycle time")
    with k5:
        late_share = (f_df["Резолюция"] == "Позже").mean() * 100 if len(f_df) else 0
        kpi_card("Позже %", f"{late_share:.1f}%", "Доля задач со статусом 'Позже' от общего числа")
    with k6:
        active_share = (
            (f_df["cycle_time"].mean() / f_df["ttm_days"].mean()) * 100
            if len(f_df) and f_df["ttm_days"].mean() > 0 else 0
        )
        kpi_card("Активная работа %", f"{active_share:.0f}%", "Доля времени, когда задача реально находилась в работе")

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
        fig_l.update_layout(height=270, xaxis_title=None, yaxis_title=None, margin=dict(l=40, r=20, t=10, b=10))
        st.plotly_chart(fig_l, use_container_width=True)

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
            margin=dict(l=40, r=20, t=10, b=10),
        )

        st.plotly_chart(fig_a, use_container_width=True)

    b1, b2, b3 = st.columns(3, gap="small")

    with b1:
        st.markdown(
            f'<div class="card-header">Динамика поступления задач</div>'
            f'<span class="hint-icon" data-hint="Количество новых задач по дням / неделям / месяцам">?</span>',
            unsafe_allow_html=True
        )
    
        daily_df = (
            f_df.set_index("Дата создания")
            .resample("D")
            .size()
            .reset_index(name="Задач")
        )
        daily_df["Группировка"] = "D"
    
        weekly_df = (
            f_df.set_index("Дата создания")
            .resample("W")
            .size()
            .reset_index(name="Задач")
        )
        weekly_df["Группировка"] = "W"
    
        monthly_df = (
            f_df.set_index("Дата создания")
            .resample("ME")
            .size()
            .reset_index(name="Задач")
        )
        monthly_df["Группировка"] = "M"
    
        fig_d = px.line(
            daily_df,
            x="Дата создания",
            y="Задач",
            markers=True,
            color_discrete_sequence=["#6244BB"],
            template="plotly_white"
        )
    
        fig_d.update_traces(visible=True, name="D")
    
        fig_d.add_scatter(
            x=weekly_df["Дата создания"],
            y=weekly_df["Задач"],
            mode="lines+markers",
            name="W",
            visible=False,
            line=dict(color="#6244BB"),
            marker=dict(color="#6244BB")
        )
    
        fig_d.add_scatter(
            x=monthly_df["Дата создания"],
            y=monthly_df["Задач"],
            mode="lines+markers",
            name="M",
            visible=False,
            line=dict(color="#6244BB"),
            marker=dict(color="#6244BB")
        )
    
        fig_d.update_layout(
            height=250,
            xaxis_title=None,
            yaxis_title=None,
            margin=dict(l=20, r=20, t=8, b=10),
            showlegend=False,
            updatemenus=[
                dict(
                    type="buttons",
                    direction="right",
                    x=0.0,
                    y=1.18,
                    xanchor="left",
                    yanchor="top",
                    showactive=True,
                    bgcolor="rgba(243,238,252,1)",
                    bordercolor="#E4DDF7",
                    borderwidth=1,
                    font=dict(size=11, color="#5D4AA8"),
                    buttons=[
                        dict(
                            label="D",
                            method="update",
                            args=[
                                {"visible": [True, False, False]},
                                {"title": None}
                            ],
                        ),
                        dict(
                            label="W",
                            method="update",
                            args=[
                                {"visible": [False, True, False]},
                                {"title": None}
                            ],
                        ),
                        dict(
                            label="M",
                            method="update",
                            args=[
                                {"visible": [False, False, True]},
                                {"title": None}
                            ],
                        ),
                    ],
                )
            ],
        )
    
        st.plotly_chart(fig_d, use_container_width=True)

    
    with b2:
        st.markdown(
            f'<div class="card-header">Передачи между командами</div>'
            f'<span class="hint-icon" data-hint="Среднее число передач задачи между командами">?</span>',
            unsafe_allow_html=True
        )

        pp = (
            f_df.groupby("Компоненты")["Пинг-понг обращения"]
            .mean()
            .reset_index()
            .sort_values("Пинг-понг обращения", ascending=True)
        )

        fig_pp = px.bar(
            pp,
            x="Пинг-понг обращения",
            y="Компоненты",
            orientation="h",
            text_auto=".1f",
            color_discrete_sequence=["#6244BB"],
            template="plotly_white"
        )

        fig_pp.update_layout(
            height=250,
            xaxis_title=None,
            yaxis_title=None,
            margin=dict(l=20, r=20, t=20, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white"
        )

        st.plotly_chart(
            fig_pp,
            use_container_width=True,
            config={"scrollZoom": False}
        )

    with b3:
        st.markdown(
            f'<div class="card-header">Структура обращений</div>'
            f'<span class="hint-icon" data-hint="Распределение задач по категориям количества обращений">?</span>',
            unsafe_allow_html=True
        )

        contacts_dist = (
            f_df["Количество обращений"]
            .value_counts(dropna=False)
            .reset_index()
        )
        contacts_dist.columns = ["Количество обращений", "Кол-во"]

        cat_order = ["1-4", "5-10", "11-100", "100+"]
        contacts_dist["Количество обращений"] = pd.Categorical(
            contacts_dist["Количество обращений"],
            categories=cat_order,
            ordered=True
        )
        contacts_dist = contacts_dist.sort_values("Количество обращений")

        fig_contacts = px.pie(
            contacts_dist,
            names="Количество обращений",
            values="Кол-во",
            hole=0.6,
            color="Количество обращений",
            color_discrete_map={
                "1-4": "#6244BB",
                "5-10": "#8B6DE0",
                "11-100": "#B39DFF",
                "100+": "#D6CCFF"
            },
            template="plotly_white"
        )

        fig_contacts.update_traces(
            textinfo="percent",
            textfont_size=12
        )

        fig_contacts.update_layout(
            height=250,
            margin=dict(l=20, r=20, t=15, b=15),
            legend_title=None,
            paper_bgcolor="white",
            plot_bgcolor="white",
            showlegend=True,
            font=dict(size=11)
        )

        st.plotly_chart(
            fig_contacts,
            use_container_width=True,
            config={"scrollZoom": False}
        )

# =========================================================
# TAB 2 — СРАВНЕНИЕ НЕДЕЛЬ
# =========================================================
with tab2:
    st.markdown(
        f"""
        <div style="font-size:16px; font-weight:600; margin-bottom:8px;">
            Текущая неделя: {cw_start.strftime('%d.%m.%Y')} — {cw_end.strftime('%d.%m.%Y')}
            <span style="color:#7E8694; font-weight:400;">&nbsp;&nbsp;vs&nbsp;&nbsp;</span>
            Предыдущая неделя: {pw_start.strftime('%d.%m.%Y')} — {pw_end.strftime('%d.%m.%Y')}
        </div>
        """,
        unsafe_allow_html=True
    )

    if not weekly_ready:
        st.warning("Недостаточно данных для сравнения текущей и предыдущей недели.")
    else:
        w1, w2, w3, w4, w5, w6, w7 = st.columns(7, gap="small")
        with w1:
            kpi_compare_card(
                "Всего задач",
                current_metrics["tasks_total"],
                previous_metrics["tasks_total"],
                hint="Количество задач за текущую неделю",
                as_int=True
            )
        with w2:
            kpi_compare_card(
                "TTM в днях",
                current_metrics["ttm"],
                previous_metrics["ttm"],
                hint="Среднее время от открытия до закрытия"
            )
        with w3:
            kpi_compare_card(
                "Cycle time (дн)",
                current_metrics["cycle"],
                previous_metrics["cycle"],
                hint="Среднее время активной работы"
            )
        with w4:
            kpi_compare_card(
                "Ожидание (дн)",
                current_metrics["wait"],
                previous_metrics["wait"],
                hint="Среднее неактивное время"
            )

        with w5:
            kpi_compare_card(
                "Позже %",
                current_metrics["later_pct"],
                previous_metrics["later_pct"],
                hint="Доля задач с резолюцией 'Позже'",
                is_percent=True
            )
        with w6:
            kpi_compare_card(
                "Активная работа %",
                current_metrics["active_pct"],
                previous_metrics["active_pct"],
                hint="Доля активной работы в общем времени",
                is_percent=True
            )
        with w7:
            kpi_compare_card(
                "Пинг-понг",
                current_metrics["pingpong"],
                previous_metrics["pingpong"],
                hint="Среднее число передач между командами"
            )

        st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)


        team_order_week = (
            pd.concat([current_week_df["Компоненты"], previous_week_df["Компоненты"]])
            .dropna()
            .value_counts()
            .index
            .tolist()
        )
        g1, g2 = st.columns(2, gap="small")

        with g1:
            st.markdown(
                f'<div class="card-header">Количество задач</div>'
                f'<span class="hint-icon" data-hint="Сравнение объёма задач по командам за две недели">?</span>',
                unsafe_allow_html=True
            )

            curr_cnt_team = current_week_df.groupby("Компоненты").size().reset_index(name="Текущая неделя")
            prev_cnt_team = previous_week_df.groupby("Компоненты").size().reset_index(name="Предыдущая неделя")
            cnt_cmp = pd.merge(curr_cnt_team, prev_cnt_team, on="Компоненты", how="outer").fillna(0)

            cnt_long = cnt_cmp.melt(
                id_vars="Компоненты",
                value_vars=["Текущая неделя", "Предыдущая неделя"],
                var_name="Период",
                value_name="Кол-во задач"
            )

            fig_cnt_compare = px.bar(
                cnt_long,
                x="Компоненты",
                y="Кол-во задач",
                color="Период",
                barmode="group",
                text_auto=".0f",
                category_orders={"Компоненты": team_order_week},
                color_discrete_map={
                    "Текущая неделя": "#6244BB",
                    "Предыдущая неделя": "#D6CCFF"
                },
                template="plotly_white"
            )
            fig_cnt_compare.update_layout(
                height=250,
                xaxis_title=None,
                yaxis_title="Кол-во задач",
                legend_title=None,
                margin=dict(l=20, r=20, t=15, b=10)
            )
            st.plotly_chart(fig_cnt_compare, use_container_width=True)

        with g2:
            st.markdown(
                f'<div class="card-header">TTM по командам</div>'
                f'<span class="hint-icon" data-hint="Сравнение среднего TTM по командам">?</span>',
                unsafe_allow_html=True
            )

            curr_ttm_team = current_week_df.groupby("Компоненты")["ttm_days"].mean().reset_index(name="Текущая неделя")
            prev_ttm_team = previous_week_df.groupby("Компоненты")["ttm_days"].mean().reset_index(name="Предыдущая неделя")
            ttm_cmp = pd.merge(curr_ttm_team, prev_ttm_team, on="Компоненты", how="outer").fillna(0)

            ttm_long = ttm_cmp.melt(
                id_vars="Компоненты",
                value_vars=["Текущая неделя", "Предыдущая неделя"],
                var_name="Период",
                value_name="TTM"
            )


            fig_ttm_compare = px.bar(
                ttm_long,
                x="Компоненты",
                y="TTM",
                color="Период",
                barmode="group",
                text_auto=".2f",
                category_orders={"Компоненты": team_order_week},
                color_discrete_map={
                    "Текущая неделя": "#6244BB",
                    "Предыдущая неделя": "#D6CCFF"
                },
                template="plotly_white"
            )
            fig_ttm_compare.update_layout(
                height=250,
                xaxis_title=None,
                yaxis_title="TTM, дней",
                legend_title=None,
                margin=dict(l=20, r=20, t=15, b=10)
            )
            st.plotly_chart(fig_ttm_compare, use_container_width=True)
            

        g3, g4 = st.columns(2, gap="small")

        with g3:
            st.markdown(
                f'<div class="card-header">Поступление задач</div>'
                f'<span class="hint-icon" data-hint="Сравнение количества новых задач по дням недели">?</span>',
                unsafe_allow_html=True
            )

            weekday_order = [0, 1, 2, 3, 4, 5, 6]
            weekday_map = {
                0: "Пн",
                1: "Вт",
                2: "Ср",
                3: "Чт",
                4: "Пт",
                5: "Сб",
                6: "Вс"
            }

            curr_daily = (
                current_week_df.assign(weekday=current_week_df["Дата создания"].dt.weekday)
                .groupby("weekday")
                .size()
                .reindex(weekday_order, fill_value=0)
                .reset_index(name="Задач")
            )
            curr_daily["Период"] = "Текущая неделя"

            prev_daily = (
                previous_week_df.assign(weekday=previous_week_df["Дата создания"].dt.weekday)
                .groupby("weekday")
                .size()
                .reindex(weekday_order, fill_value=0)
                .reset_index(name="Задач")
            )
            prev_daily["Период"] = "Предыдущая неделя"

            weekly_flow = pd.concat([curr_daily, prev_daily], ignore_index=True)
            weekly_flow["День"] = weekly_flow["weekday"].map(weekday_map)

            fig_flow = px.line(
                weekly_flow,
                x="День",
                y="Задач",
                color="Период",
                markers=True,
                category_orders={"День": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]},
                color_discrete_map={
                    "Текущая неделя": "#6244BB",
                    "Предыдущая неделя": "#D6CCFF"
                },
                template="plotly_white"
            )

            fig_flow.update_layout(
                height=230,
                xaxis_title=None,
                yaxis_title="Кол-во задач",
                legend_title=None,
                margin=dict(l=20, r=20, t=15, b=10)
            )

            st.plotly_chart(fig_flow, use_container_width=True)

        with g4:
            st.markdown(
                f'<div class="card-header">Количество обращений</div>'
                f'<span class="hint-icon" data-hint="Сравнение категорий количества обращений за две недели">?</span>',
                unsafe_allow_html=True
            )

            cat_order = ["1-4", "5-10", "11-100", "100+"]

            curr_contacts = (
                current_week_df["Количество обращений"]
                .value_counts()
                .reindex(cat_order, fill_value=0)
                .reset_index()
            )
            curr_contacts.columns = ["Количество обращений", "Кол-во"]
            curr_contacts["Период"] = "Текущая неделя"

            prev_contacts = (
                previous_week_df["Количество обращений"]
                .value_counts()
                .reindex(cat_order, fill_value=0)
                .reset_index()
            )
            prev_contacts.columns = ["Количество обращений", "Кол-во"]
            prev_contacts["Период"] = "Предыдущая неделя"

            contacts_compare = pd.concat([curr_contacts, prev_contacts], ignore_index=True)

            fig_contacts_compare = px.bar(
                contacts_compare,
                x="Количество обращений",
                y="Кол-во",
                color="Период",
                barmode="group",
                text_auto=".0f",
                category_orders={"Количество обращений": cat_order},
                color_discrete_map={
                    "Текущая неделя": "#6244BB",
                    "Предыдущая неделя": "#D6CCFF"
                },
                template="plotly_white"
            )

            fig_contacts_compare.update_layout(
                height=230,
                xaxis_title=None,
                yaxis_title="Кол-во задач",
                legend_title=None,
                margin=dict(l=20, r=20, t=15, b=10)
            )

            st.plotly_chart(fig_contacts_compare, use_container_width=True)
