import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import yadisk
import os
from datetime import timedelta, date
import plotly.graph_objects as go

st.set_page_config(page_title="Аналитика дежурств", layout="wide")
ACCESS_TOKEN = st.secrets["ACCESS_TOKEN"]
token = st.query_params.get("token")

if token != ACCESS_TOKEN:
    st.markdown("## Доступ ограничен")
    st.error("Эта ссылка недействительна или у вас нет доступа.")
    st.stop()


TTM_STAGES = ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]
CYCLE_STAGES = ["Бэклог разработки", "В работе"]
WAIT_STAGES = [stage for stage in TTM_STAGES if stage not in CYCLE_STAGES]


# 2) BI-стиль + тултипы + sidebar chips + календарь
st.markdown(
    """
    <style>

    header[data-testid="stHeader"] {
        background: #F7F2FA !important;
        height: 1.6rem !important;
        min-height: 1.6rem !important;
    }

    /* Нижний floating launcher / Manage app */
    [data-testid="stStatusWidget"] {
        display: none !important;
        visibility: hidden !important;
    }

    button[title="Manage app"] {
        display: none !important;
        visibility: hidden !important;
    }

    button[aria-label="Manage app"] {
        display: none !important;
        visibility: hidden !important;
    }

    div[style*="position: fixed"][style*="bottom"] {
        z-index: 0 !important;
    }

    div[style*="position: fixed"][style*="bottom"] button {
        display: none !important;
        visibility: hidden !important;
    }

    iframe[title*="Manage app"],
    iframe[title*="Streamlit"] {
        display: none !important;
        visibility: hidden !important;
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

    [data-baseweb="select"] > div {
        background-color: white !important;
        border-radius: 14px !important;
        border: none !important;
        min-height: 48px !important;
    }

    [data-baseweb="select"] input { color: #1A1C1E !important; }

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

    [data-baseweb="select"] svg { fill: #6244BB !important; }

    [data-baseweb="select"] > div:hover { box-shadow: 0 0 0 1px #6244BB inset !important; }
    [data-baseweb="select"] > div:focus-within { box-shadow: 0 0 0 2px #6244BB inset !important; }

    /* ===================== DATE INPUT ===================== */
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
        padding-top: 0.45rem !important;
        padding-bottom: 0.25rem !important;
        padding-left: 0.45rem !important;
        padding-right: 0.45rem !important;
        max-width: 100% !important;
    }

    div[data-testid="stVerticalBlock"] > div {
        gap: 0.6rem;
    }

    .main-header { font-size: 24px; font-weight: 800; color: #1A1C1E; margin: 0 0 10px 0; }
    .card-header { font-size: 14px; font-weight: 700; color: #1A1C1E; display: inline-block; }

    .kpi-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 12px 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        text-align: left;
        height: 100px;
        display: grid;
        grid-template-rows: auto 1fr auto;
        align-items: stretch;
    }

    .kpi-title {
        font-size: 15px;
        font-weight: 650;
        color: #1A1C1E;
        line-height: 1.2;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        min-height: 0;
        margin: 0;
    }

    .kpi-value {
        font-size: 26px;
        font-weight: 650;
        color: #6244BB;
        line-height: 1;
        margin: 0;
        display: flex;
        align-items: center;
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
        flex: 0 0 auto;
    }

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

    [data-testid="stPlotlyChart"] {
        background: white;
        border-radius: 18px;
        padding: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        border: 1px solid #ECEAF3;
        overflow: hidden;
    }

    th {
        background-color: #6244BB !important;
        color: white !important;
        font-weight: 600 !important;
        text-align: left !important;
    }
    thead tr th:first-child { display:none; }
    tbody tr th:first-child { display:none; }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        margin-bottom: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        min-height: 28px !important;
        height: 28px !important;
        min-width: 90px !important;
        padding: 0px 10px !important;
        background: #F3EEFC;
        border-radius: 5px;
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

    div[role="radiogroup"] {
        gap: 8px;
    }

    div[role="radiogroup"] label {
        background: #F3EEFC !important;
        border: 1px solid #E4DDF7 !important;
        border-radius: 10px !important;
        padding: 6px 12px !important;
        margin-right: 6px !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


def kpi_card(title: str, value: str, hint: str = "", subvalue: str = "", color: str = "#6244BB"):
    hint_html = f'<span class="hint-icon" data-hint="{hint}">?</span>' if hint else ""
    sub_html = (
        f'<div style="font-size:13px; color:#7E8694; line-height:1.2;">{subvalue}</div>'
        if subvalue else ""
    )

    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title} {hint_html}</div>
            <div class="kpi-value" style="color:{color};">{value}</div>
            {sub_html}
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
        <div class="kpi-card" style="height: 120px; padding: 6px 10px;">
            <div class="kpi-title" style="font-size:14px; min-height:22px;">
                {title} {hint_html}
            </div>
            <div class="kpi-value" style="font-size:22px; line-height:1;">
                {current_str}
            </div>
            <div style="font-size:15px; color:#7E8694; margin-top:2px; line-height:1;">
                Пред. неделя: {previous_str}
            </div>
            <div style="font-size:15px; font-weight:700; color:#4F46E5; margin-top:3px; line-height:1;">
                Изменение: {diff_str}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def get_week_bounds(anchor_date):
    anchor_date = pd.Timestamp(anchor_date).normalize()
    current_week_start = anchor_date - pd.Timedelta(days=6)
    current_week_end = anchor_date + pd.Timedelta(hours=23, minutes=59, seconds=59)
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
            "pingpong_share": 0.0
        }

    ttm_mean = df_["ttm_days"].mean() if "ttm_days" in df_.columns else 0.0
    cycle_mean = df_["cycle_time"].mean() if "cycle_time" in df_.columns else 0.0
    wait_mean = df_["wait_time_days"].mean() if "wait_time_days" in df_.columns else 0.0
    later_pct = (df_["Резолюция"] == "Позже").mean() * 100 if "Резолюция" in df_.columns else 0.0
    active_pct = (cycle_mean / ttm_mean * 100) if ttm_mean > 0 else 0.0
    pingpong_share = (
        (df_["Пинг-понг обращения"] > 1).mean() * 100
        if "Пинг-понг обращения" in df_.columns else 0.0
    )

    return {
        "tasks_total": len(df_),
        "ttm": ttm_mean,
        "cycle": cycle_mean,
        "wait": wait_mean,
        "later_pct": later_pct,
        "active_pct": active_pct,
        "pingpong_share": pingpong_share
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

    for col in set(TTM_STAGES + CYCLE_STAGES):
        if col not in df_.columns:
            df_[col] = 0
        df_[col] = pd.to_numeric(df_[col], errors="coerce").fillna(0)

    df_["ttm_days"] = df_[TTM_STAGES].sum(axis=1) / 1440
    df_["cycle_time"] = df_[CYCLE_STAGES].sum(axis=1) / 1440
    df_["wait_time_days"] = (df_["ttm_days"] - df_["cycle_time"]).clip(lower=0)

    df_["Резолюция"] = df_.get("Резолюция", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Компоненты"] = df_.get("Компоненты", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Приоритет"] = df_.get("Приоритет", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")
    df_["Пинг-понг обращения"] = pd.to_numeric(df_.get("Пинг-понг обращения", 0), errors="coerce").fillna(0)
    df_["Количество обращений"] = df_.get("Количество обращений", pd.Series(["Не указано"] * len(df_))).fillna("Не указано")

    if "Тип" not in df_.columns:
        df_["Тип"] = "Не указано"
    df_["Тип"] = df_["Тип"].fillna("Не указано").astype(str).str.strip()

    return df_


df = load_data()
if df.empty:
    st.warning("Данные не найдены.")
    st.stop()

# ===================== SIDEBAR FILTERS =====================
db_min = df["Дата создания"].min().date()
db_max = df["Дата создания"].max().date()

default_start = max(db_min, db_max - timedelta(days=6))
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
types_in_range = sorted(df_in_range["Тип"].dropna().unique().tolist())

period_sig = (start_date, end_date)

if st.session_state.get("_period_sig") != period_sig:
    st.session_state["_period_sig"] = period_sig
    st.session_state["sel_teams"] = teams_in_range
    st.session_state["sel_res"] = res_in_range
    st.session_state["sel_types"] = types_in_range

sel_teams = st.sidebar.multiselect(
    "Команды",
    teams_in_range,
    default=st.session_state.get("sel_teams", teams_in_range),
    key="sel_teams"
)

sel_res = st.sidebar.multiselect(
    "Резолюции",
    res_in_range,
    default=st.session_state.get("sel_res", res_in_range),
    key="sel_res"
)

sel_types = st.sidebar.multiselect(
    "Тип",
    types_in_range,
    default=st.session_state.get("sel_types", types_in_range),
    key="sel_types"
)

f_df = df_in_range[
    (df_in_range["Компоненты"].isin(sel_teams)) &
    (df_in_range["Резолюция"].isin(sel_res)) &
    (df_in_range["Тип"].isin(sel_types))
].copy()

if f_df.empty:
    st.warning("По выбранным фильтрам данных нет.")
    st.stop()

# ===================== WEEKLY COMPARISON DATA =====================
base_week_df = df[
    (df["Компоненты"].isin(sel_teams)) &
    (df["Резолюция"].isin(sel_res)) &
    (df["Тип"].isin(sel_types))
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
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7, gap="small")

    with k1:
        kpi_card("Всего задач", f"{len(f_df)}", "Общее число задач за выбранный период, которые поступили в работу")

    with k2:
        med = f_df["ttm_days"].median() if len(f_df) else 0.0
        avg = f_df["ttm_days"].mean() if len(f_df) else 0.0
        kpi_card(
            "TTM (дн)",
            f"{avg:.2f}",
            "Сколько в среднем времени занимал путь задач по процессу целиком, считается в днях. Так же тут указана медиана, она показывает более “типичное” значение",
            subvalue=f"медиана: {med:.2f}"
        )

    with k3:
        med = f_df["cycle_time"].median() if len(f_df) else 0.0
        avg = f_df["cycle_time"].mean() if len(f_df) else 0.0
        kpi_card(
            "Cycle time (дн)",
            f"{avg:.2f}",
            "Среднее время активной работы над задачами, считается в днях. Также тут указана медиана, она показывает более “типичное” значение",
            subvalue=f"медиана: {med:.2f}"
        )

    with k4:
        avg = f_df["wait_time_days"].mean() if len(f_df) else 0.0
        med = f_df["wait_time_days"].median() if len(f_df) else 0.0
        kpi_card(
            "Ожидание (дн)",
            f"{avg:.2f}",
            "Среднее время, которое задача проводила вне активной работы. (Среднее ожидание = среднее значение разницы между TTM и Cycle time). Медиана показывает более “типичное” значение",
            subvalue=f"медиана: {med:.2f}"
        )

    with k5:
        late = ((f_df["Резолюция"] == "Позже").mean() * 100) if len(f_df) else 0
        late_color = "#E45757" if late > 50 else "#4CAF7D"
        kpi_card(
            "Позже",
            f"{late:.1f}%",
            "Доля задач, которые решены позже",
            color=late_color
        )

    with k6:
        active = (
            (f_df["cycle_time"].sum() / f_df["ttm_days"].sum()) * 100
            if f_df["ttm_days"].sum() > 0 else 0
        )
        active_color = "#E45757" if active < 50 else "#4CAF7D"
        kpi_card(
            "Flow Efficiency",
            f"{active:.0f}%",
            "Доля активной работы в общем времени работы над задачей, то есть cycle time/ TTM",
            color=active_color
        )

    with k7:
        pingpong_share = (
            (f_df["Пинг-понг обращения"] > 1).mean() * 100
            if len(f_df) else 0.0
        )
        tasks_with_pingpong = (
            (f_df["Пинг-понг обращения"] > 1).sum()
            if len(f_df) else 0
        )
        pingpong_color = "#E45757" if pingpong_share > 20 else "#4CAF7D"
    
        kpi_card(
            "Пинг-понг > 1",
            f"{pingpong_share:.1f}%",
            "Доля задач, которые\n\nпередавались между командами\n\nболее одного раза,\n\nесли была только одна команда,\n\nто стоит 1",
            subvalue=f"задач: {tasks_with_pingpong}",
            color=pingpong_color
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="small")

    time_order_df = (
        f_df.groupby("Компоненты")["ttm_days"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    t_order = time_order_df["Компоненты"].tolist()

    with c1:
        st.markdown(
            f'<div class="card-header">Структура времени задач по командам</div>'
            f'<span class="hint-icon" data-hint="Можно посмотреть суммарно Cycle time + ожидание (позволяет понять соотношение активной работы и ожидания)  или только этапы ожидания (позволяет понять где и почему задержалось выполнение задачи)">?</span>',
            unsafe_allow_html=True
        )

        team_stage_avg = f_df.groupby("Компоненты").mean(numeric_only=True).reset_index()

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

        name_map = {
            "cycle_time": "Cycle time",
            "wait_time_days": "Ожидание"
        }
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
            color_discrete_map={
                "Cycle time": "#6244BB",
                "Ожидание": "#A485E0"
            },
            template="plotly_white",
        )

        wait_colors = {
            "Сбор данных": "#5B3FC4",
            "Открыт": "#8A6BE8",
            "Заблокирован": "#B59AF5",
            "На стороне менеджера": "#E3D9FF"
        }

        for stage in WAIT_STAGES:
            stage_df = pd.DataFrame({
                "Компоненты": team_stage_avg["Компоненты"],
                "Дни": team_stage_avg[stage] / 1440
            })

            fig_a.add_bar(
                x=stage_df["Дни"],
                y=stage_df["Компоненты"],
                name=stage,
                orientation="h",
                marker_color=wait_colors.get(stage, "#A485E0"),
                text=[f"{x:.1f}" if x > 0 else "" for x in stage_df["Дни"]],
                textposition="auto",
                visible=False
            )

        visible_sum = [True, True] + [False] * len(WAIT_STAGES)
        visible_wait = [False, False] + [True] * len(WAIT_STAGES)

        fig_a.update_layout(
            height=270,
            xaxis_title=None,
            yaxis_title=None,
            legend_title=None,
            margin=dict(l=40, r=20, t=10, b=10),
            updatemenus=[
                dict(
                    type="buttons",
                    direction="right",
                    x=0.98,
                    y=0.08,
                    xanchor="right",
                    yanchor="bottom",
                    showactive=True,
                    bgcolor="rgba(243,238,252,0.95)",
                    bordercolor="#E4DDF7",
                    borderwidth=1,
                    font=dict(size=9, color="#5D4AA8"),
                    pad=dict(r=0, t=0, l=0, b=0),
                    buttons=[
                        dict(
                            label="Суммарно",
                            method="update",
                            args=[
                                {"visible": visible_sum},
                                {"barmode": "stack"}
                            ],
                        ),
                        dict(
                            label="Ожидание",
                            method="update",
                            args=[
                                {"visible": visible_wait},
                                {"barmode": "stack"}
                            ],
                        ),
                    ],
                )
            ],
        )

        st.plotly_chart(fig_a, use_container_width=True)

    with c2:
        st.markdown(
            f'<div class="card-header">Нагрузка по командам</div>'
            f'<span class="hint-icon" data-hint="Количество задач, которые были взяты в работу по командам">?</span>',
            unsafe_allow_html=True
        )

        t_counts = f_df.groupby("Компоненты").size().reset_index(name="Кол-во")
        fig_l = px.bar(
            t_counts,
            x="Кол-во",
            y="Компоненты",
            orientation="h",
            text="Кол-во",
            category_orders={"Компоненты": t_order},
            color_discrete_sequence=["#6244BB"],
            template="plotly_white"
        )
        fig_l.update_layout(
            height=270,
            xaxis_title=None,
            yaxis_title=None,
            showlegend=False,
            margin=dict(l=40, r=20, t=10, b=10)
        )
        st.plotly_chart(fig_l, use_container_width=True)

    b1, b2, b3 = st.columns(3, gap="small")

    with b1:
        st.markdown(
            f'<div class="card-header">Динамика поступления задач</div>'
            f'<span class="hint-icon" data-hint="Количество новых задач по дням / неделям / месяцам. Так же выходные на графике выделены красным, что помогает понять была ли работа в выходные">?</span>',
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

        weekend_df = daily_df[daily_df["Дата создания"].dt.weekday.isin([5, 6])].copy()

        fig_d = px.line(
            daily_df,
            x="Дата создания",
            y="Задач",
            markers=True,
            color_discrete_sequence=["#6244BB"],
            template="plotly_white"
        )

        fig_d.update_traces(
            visible=True,
            name="D",
            line=dict(color="#6244BB"),
            marker=dict(color="#6244BB", size=7),
            hovertemplate="Дата: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>"
        )

        fig_d.add_scatter(
            x=weekend_df["Дата создания"],
            y=weekend_df["Задач"],
            mode="markers",
            name="Выходные",
            visible=True,
            marker=dict(
                color="#E45757",
                size=8,
                line=dict(color="white", width=1)
            ),
            hovertemplate="Выходной<br>Дата: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>"
        )

        fig_d.add_scatter(
            x=weekly_df["Дата создания"],
            y=weekly_df["Задач"],
            mode="lines+markers",
            name="W",
            visible=False,
            line=dict(color="#6244BB"),
            marker=dict(color="#6244BB", size=7),
            hovertemplate="Неделя до: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>"
        )

        fig_d.add_scatter(
            x=monthly_df["Дата создания"],
            y=monthly_df["Задач"],
            mode="lines+markers",
            name="M",
            visible=False,
            line=dict(color="#6244BB"),
            marker=dict(color="#6244BB", size=7),
            hovertemplate="Месяц: %{x|%m.%Y}<br>Задач: %{y}<extra></extra>"
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
                    font=dict(size=10, color="#5D4AA8"),
                    pad=dict(r=0, t=0),
                    buttons=[
                        dict(
                            label="D",
                            method="update",
                            args=[
                                {"visible": [True, True, False, False]},
                                {"title": None}
                            ],
                        ),
                        dict(
                            label="W",
                            method="update",
                            args=[
                                {"visible": [False, False, True, False]},
                                {"title": None}
                            ],
                        ),
                        dict(
                            label="M",
                            method="update",
                            args=[
                                {"visible": [False, False, False, True]},
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
            f'<div class="card-header">Распределение времени задач</div>'
            f'<span class="hint-icon" data-hint="Можно посмотреть распределение TTM, Cycle time или ожидания по задачам, это позволяет более подробно взглянуть на метрики и посмотреть нет ли тяжелых хвостов">?</span>',
            unsafe_allow_html=True
        )
    
        dist_df = f_df[["ttm_days", "cycle_time", "wait_time_days"]].dropna().copy()
    
        fig_dist = go.Figure()
    
        # 0 — TTM
        fig_dist.add_trace(
            go.Histogram(
                x=dist_df["ttm_days"],
                name="TTM",
                marker_color="#6244BB",
                opacity=0.85,
                nbinsx=20,
                visible=True
            )
        )
    
        # 1 — Cycle time
        fig_dist.add_trace(
            go.Histogram(
                x=dist_df["cycle_time"],
                name="Cycle time",
                marker_color="#6244BB",
                opacity=0.85,
                nbinsx=20,
                visible=False
            )
        )
    
        # 2 — Ожидание
        fig_dist.add_trace(
            go.Histogram(
                x=dist_df["wait_time_days"],
                name="Ожидание",
                marker_color="#A485E0",
                opacity=0.85,
                nbinsx=20,
                visible=False
            )
        )
    
        fig_dist.update_layout(
            height=250,
            xaxis_title="Дни",
            yaxis_title="Количество задач",
            legend_title=None,
            margin=dict(l=20, r=20, t=20, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            bargap=0.08,
            template="plotly_white",
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
                    font=dict(size=10, color="#5D4AA8"),
                    pad=dict(r=0, t=0),
                    buttons=[
                        dict(
                            label="TTM",
                            method="update",
                            args=[
                                {"visible": [True, False, False]},
                                {
                                    "xaxis": {"title": "TTM, дни"},
                                    "yaxis": {"title": "Количество задач"}
                                }
                            ],
                        ),
                        dict(
                            label="Cycle time",
                            method="update",
                            args=[
                                {"visible": [False, True, False]},
                                {
                                    "xaxis": {"title": "Cycle time, дни"},
                                    "yaxis": {"title": "Количество задач"}
                                }
                            ],
                        ),
                        dict(
                            label="Ожидание",
                            method="update",
                            args=[
                                {"visible": [False, False, True]},
                                {
                                    "xaxis": {"title": "Ожидание, дни"},
                                    "yaxis": {"title": "Количество задач"}
                                }
                            ],
                        ),
                    ],
                )
            ],
        )
    
        st.plotly_chart(
            fig_dist,
            use_container_width=True,
            config={"scrollZoom": False}
        )

    with b3:
        st.markdown(
            f'<div class="card-header">Структура обращений</div>'
            f'<span class="hint-icon" data-hint="Распределение задач по категориям количества обращений. Смотрим только в типе запрос на обслуживание">?</span>',
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
                "1-4": "#5B3FC4",
                "5-10": "#8C6FF0",
                "11-100": "#B9A3FA",
                "100+": "#E1D8FF"
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
                hint="Количество задач за текущую неделю выделено фиолетовым цветом, также есть значение за предыдущую неделю и разница между значениями",
                as_int=True
            )
        with w2:
            kpi_compare_card(
                "TTM (дн)",
                current_metrics["ttm"],
                previous_metrics["ttm"],
                hint="Среднее время от открытия задачи до её закрытия за текущую неделю выделено фиолетовым цветом, также есть значение за предыдущую неделю и разница между значениями"
            )
        with w3:
            kpi_compare_card(
                "Cycle time (дн)",
                current_metrics["cycle"],
                previous_metrics["cycle"],
                hint="Среднее время активной работы над задачей за текущую неделю выделено фиолетовым цветом, также есть значение за предыдущую неделю и разница между значениями"
            )
        with w4:
            kpi_compare_card(
                "Ожидание (дн)",
                current_metrics["wait"],
                previous_metrics["wait"],
                hint="Среднее время, которое задачи находились в ожидании за текущую неделю выделено фиолетовым цветом, также есть значение за предыдущую неделю и разница между значениями"
            )
        with w5:
            kpi_compare_card(
                "Позже",
                current_metrics["later_pct"],
                previous_metrics["later_pct"],
                hint="Доля задач с резолюцией 'Позже' за текущую неделю выделено фиолетовым цветом, также есть значение за предыдущую неделю и разница между значениями",
                is_percent=True
            )
        with w6:
            kpi_compare_card(
                "Flow Efficiency",
                current_metrics["active_pct"],
                previous_metrics["active_pct"],
                hint="Доля активной работы в общем времени за текущую неделю выделено фиолетовым цветом, также есть значение за предыдущую неделю и разница между значениями",
                is_percent=True
            )
        with w7:
            kpi_compare_card(
                "Пинг-понг > 1",
                current_metrics["pingpong_share"],
                previous_metrics["pingpong_share"],
                hint="Доля задач, которые передавались между командами более одного раза за текущую неделю выделено фиолетовым цветом, также есть значение за предыдущую неделю и разница между значениями",
                is_percent=True
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
                height=260,
                xaxis_title=None,
                yaxis_title="Кол-во задач",
                legend_title=None,
                margin=dict(l=20, r=20, t=15, b=10)
            )
            st.plotly_chart(fig_cnt_compare, use_container_width=True)

        with g2:
            st.markdown(
                f'<div class="card-header">TTM по командам</div>'
                f'<span class="hint-icon" data-hint="Можно посмотреть TTM, только Cycle time или только ожидание по командам за текущую и предыдущую недели">?</span>',
                unsafe_allow_html=True
            )
        
            curr_parts = (
                current_week_df.groupby("Компоненты")[["ttm_days", "cycle_time", "wait_time_days"]]
                .mean()
                .reindex(team_order_week, fill_value=0)
                .reset_index()
            )
        
            prev_parts = (
                previous_week_df.groupby("Компоненты")[["ttm_days", "cycle_time", "wait_time_days"]]
                .mean()
                .reindex(team_order_week, fill_value=0)
                .reset_index()
            )
        
            fig_ttm_compare = go.Figure()
        
            # 0 — TTM current
            fig_ttm_compare.add_trace(
                go.Bar(
                    x=curr_parts["Компоненты"],
                    y=curr_parts["ttm_days"],
                    name="TTM — текущая",
                    marker_color="#6244BB",
                    text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["ttm_days"]],
                    textposition="outside",
                    cliponaxis=False,
                    visible=True
                )
            )
        
            # 1 — TTM previous
            fig_ttm_compare.add_trace(
                go.Bar(
                    x=prev_parts["Компоненты"],
                    y=prev_parts["ttm_days"],
                    name="TTM — предыдущая",
                    marker_color="#D6CCFF",
                    text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["ttm_days"]],
                    textposition="outside",
                    cliponaxis=False,
                    visible=True
                )
            )
        
            # 2 — Cycle current
            fig_ttm_compare.add_trace(
                go.Bar(
                    x=curr_parts["Компоненты"],
                    y=curr_parts["cycle_time"],
                    name="Cycle time — текущая",
                    marker_color="#6244BB",
                    text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["cycle_time"]],
                    textposition="outside",
                    cliponaxis=False,
                    visible=False
                )
            )
        
            # 3 — Cycle previous
            fig_ttm_compare.add_trace(
                go.Bar(
                    x=prev_parts["Компоненты"],
                    y=prev_parts["cycle_time"],
                    name="Cycle time — предыдущая",
                    marker_color="#D6CCFF",
                    text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["cycle_time"]],
                    textposition="outside",
                    cliponaxis=False,
                    visible=False
                )
            )
        
            # 4 — Wait current
            fig_ttm_compare.add_trace(
                go.Bar(
                    x=curr_parts["Компоненты"],
                    y=curr_parts["wait_time_days"],
                    name="Ожидание — текущая",
                    marker_color="#A485E0",
                    text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["wait_time_days"]],
                    textposition="outside",
                    cliponaxis=False,
                    visible=False
                )
            )
        
            # 5 — Wait previous
            fig_ttm_compare.add_trace(
                go.Bar(
                    x=prev_parts["Компоненты"],
                    y=prev_parts["wait_time_days"],
                    name="Ожидание — предыдущая",
                    marker_color="#EEE8FF",
                    text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["wait_time_days"]],
                    textposition="outside",
                    cliponaxis=False,
                    visible=False
                )
            )
        
            fig_ttm_compare.update_layout(
                height=260,
                xaxis_title=None,
                yaxis_title="TTM, дней",
                legend_title=None,
                margin=dict(l=20, r=20, t=15, b=10),
                barmode="group",
                template="plotly_white",
                uniformtext_minsize=9,
                uniformtext_mode="hide",
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
                        font=dict(size=10, color="#5D4AA8"),
                        pad=dict(r=0, t=0),
                        buttons=[
                            dict(
                                label="TTM",
                                method="update",
                                args=[
                                    {"visible": [True, True, False, False, False, False]},
                                    {
                                        "barmode": "group",
                                        "yaxis": {"title": "TTM, дней"}
                                    }
                                ],
                            ),
                            dict(
                                label="Cycle time",
                                method="update",
                                args=[
                                    {"visible": [False, False, True, True, False, False]},
                                    {
                                        "barmode": "group",
                                        "yaxis": {"title": "Cycle time, дней"}
                                    }
                                ],
                            ),
                            dict(
                                label="Ожидание",
                                method="update",
                                args=[
                                    {"visible": [False, False, False, False, True, True]},
                                    {
                                        "barmode": "group",
                                        "yaxis": {"title": "Ожидание, дней"}
                                    }
                                ],
                            ),
                        ],
                    )
                ],
            )
        
            st.plotly_chart(fig_ttm_compare, use_container_width=True)

        g3, g4 = st.columns(2, gap="small")

        with g3:
            st.markdown(
                f'<div class="card-header">Поступление задач</div>'
                f'<span class="hint-icon" data-hint="Сравнение количества новых задач по дням для текущей недели и предыдущей">?</span>',
                unsafe_allow_html=True
            )

            current_dates = pd.date_range(cw_start.normalize(), cw_end.normalize(), freq="D")
            previous_dates = pd.date_range(pw_start.normalize(), pw_end.normalize(), freq="D")

            weekday_map = {
                0: "Пн",
                1: "Вт",
                2: "Ср",
                3: "Чт",
                4: "Пт",
                5: "Сб",
                6: "Вс"
            }

            x_labels = [weekday_map[d.weekday()] for d in current_dates]

            curr_daily = (
                current_week_df.assign(Дата=current_week_df["Дата создания"].dt.normalize())
                .groupby("Дата")
                .size()
                .reindex(current_dates, fill_value=0)
                .reset_index(name="Задач")
            )
            curr_daily.columns = ["Дата", "Задач"]
            curr_daily["X"] = x_labels
            curr_daily["Период"] = "Текущая неделя"

            prev_daily = (
                previous_week_df.assign(Дата=previous_week_df["Дата создания"].dt.normalize())
                .groupby("Дата")
                .size()
                .reindex(previous_dates, fill_value=0)
                .reset_index(name="Задач")
            )
            prev_daily.columns = ["Дата", "Задач"]
            prev_daily["X"] = x_labels
            prev_daily["Период"] = "Предыдущая неделя"

            weekly_flow = pd.concat([curr_daily, prev_daily], ignore_index=True)

            fig_flow = px.line(
                weekly_flow,
                x="X",
                y="Задач",
                color="Период",
                markers=True,
                category_orders={"X": x_labels},
                color_discrete_map={
                    "Текущая неделя": "#6244BB",
                    "Предыдущая неделя": "#D6CCFF"
                },
                template="plotly_white"
            )

            fig_flow.update_layout(
                height=220,
                xaxis_title=None,
                yaxis_title="Кол-во задач",
                legend_title=None,
                margin=dict(l=20, r=20, t=15, b=10)
            )

            st.plotly_chart(fig_flow, use_container_width=True)

        with g4:
            st.markdown(
                f'<div class="card-header">Количество обращений</div>'
                f'<span class="hint-icon" data-hint="Сравнение категорий количества обращений за две недели, смотрим только в типе запрос на обслуживание">?</span>',
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
                height=220,
                xaxis_title=None,
                yaxis_title="Кол-во задач",
                legend_title=None,
                margin=dict(l=20, r=20, t=15, b=10)
            )

            st.plotly_chart(fig_contacts_compare, use_container_width=True)
