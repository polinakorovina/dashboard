import io
from datetime import timedelta, date

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader

from data_pipeline import (
    load_single_file,
    load_and_prepare_two_dataframes,
    prepare_dashboard_data,
    read_dashboard_from_postgres,
    read_meta_from_postgres,
    write_dashboard_to_postgres_append,
)

st.set_page_config(page_title="Аналитика дежурств", layout="wide")

ACCESS_TOKEN = st.secrets["ACCESS_TOKEN"]
POSTGRES_URL = st.secrets["POSTGRES_URL"]

token = st.query_params.get("token")

if token != ACCESS_TOKEN:
    st.markdown("## Доступ ограничен")
    st.error("Эта ссылка недействительна или у вас нет доступа.")
    st.stop()

TTM_STAGES = [
    "Сбор данных",
    "Открыт",
    "Заблокирован",
    "На стороне менеджера",
    "Бэклог разработки",
    "В работе"
]
CYCLE_STAGES = ["Бэклог разработки", "В работе"]
WAIT_STAGES = [stage for stage in TTM_STAGES if stage not in CYCLE_STAGES]

WAIT_COLORS = {
    "Сбор данных": "#5B3FC4",
    "Открыт": "#8A6BE8",
    "Заблокирован": "#B59AF5",
    "На стороне менеджера": "#E3D9FF"
}

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] {
        background: #F7F2FA !important;
        height: 1.6rem !important;
        min-height: 1.6rem !important;
    }

    [data-testid="stStatusWidget"] {
        display: none !important;
        visibility: hidden !important;
    }

    div[style*="position: fixed"][style*="bottom"] {
        display: none !important;
        visibility: hidden !important;
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

    footer {
        display: none !important;
        visibility: hidden !important;
    }

    .stApp { background-color: #F7F2FA; }

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

    .main-header {
        font-size: 24px;
        font-weight: 800;
        color: #1A1C1E;
        margin: 0;
        padding-top: 6px;
    }

    .card-header {
        font-size: 14px;
        font-weight: 700;
        color: #1A1C1E;
        display: inline-block;
    }

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
        left: 80%;
        transform: translateX(-80%);
        background-color: #1A1C1E;
        color: #fff;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 12px;
        width: 180px;
        max-width: min(180px, calc(100vw - 24px));
        white-space: normal;
        word-break: break-word;
        z-index: 1000;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        font-weight: normal;
        pointer-events: none;
    }

    [data-testid="column"]:first-child .hint-icon:hover::after {
        left: 0;
        right: auto;
        transform: none;
    }

    [data-testid="column"]:last-child .hint-icon:hover::after {
        right: 0;
        left: auto;
        transform: none;
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

    div[role="radiogroup"] {
        gap: 8px;
    }

    div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    div[role="radiogroup"] label {
        background: #F3EEFC !important;
        border: 1px solid #E4DDF7 !important;
        border-radius: 10px !important;
        padding: 6px 12px !important;
        margin-right: 6px !important;
    }

    div[role="radiogroup"] label[data-checked="true"] {
        background: white !important;
        border: 1px solid #D8CDF4 !important;
        box-shadow: 0 1px 4px rgba(98, 68, 187, 0.06);
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] > button {
        border-radius: 9px !important;
        border: 1px solid #D8CDF4 !important;
        background: white !important;
        color: #6244BB !important;
        font-weight: 600 !important;
        min-height: 34px !important;
        padding: 0.20rem 0.75rem !important;
        font-size: 10px !important;
        width: auto !important;
        white-space: nowrap !important;
    }

    .compare-card {
        background: #ffffff;
        border: 1px solid #E6E9EF;
        border-radius: 16px;
        padding: 8px 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        height: 116px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .compare-title {
        font-size: 13px;
        font-weight: 650;
        color: #1A1C1E;
        line-height: 1.1;
        margin: 0;
    }

    .compare-value {
        font-size: 20px;
        font-weight: 700;
        color: #6244BB;
        line-height: 1;
        margin: 0;
    }

    .compare-sub {
        font-size: 12px;
        color: #7E8694;
        line-height: 1.1;
        margin: 0;
    }

    .compare-delta {
        font-size: 12px;
        font-weight: 700;
        color: #4F46E5;
        line-height: 1.1;
        margin: 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ===================== HELPERS =====================

def kpi_card(title: str, value: str, hint: str = "", subvalue: str = "", color: str = "#6244BB", hint_side: str = "center"):
    hint_html = f'<span class="hint-icon hint-{hint_side}" data-hint="{hint}">?</span>' if hint else ""
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


def kpi_compare_card(title, current, previous, hint="", is_percent=False, as_int=False, digits=2, hint_side="center"):
    current_str = format_value(current, is_percent=is_percent, digits=digits, as_int=as_int)
    previous_str = format_value(previous, is_percent=is_percent, digits=digits, as_int=as_int)
    diff_str = delta_text(current, previous, is_percent=is_percent, digits=digits)
    hint_html = f'<span class="hint-icon hint-{hint_side}" data-hint="{hint}">?</span>' if hint else ""

    st.markdown(
        f"""
        <div class="compare-card">
            <div class="compare-title">{title} {hint_html}</div>
            <div class="compare-value">{current_str}</div>
            <div class="compare-sub">Пред. неделя: {previous_str}</div>
            <div class="compare-delta">Изменение: {diff_str}</div>
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


def safe_get_state(name, default):
    return st.session_state.get(name, default)


def get_period_days(start_date, end_date):
    return (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1


def get_default_granularity(period_days: int):
    if period_days > 183:
        return "M"
    if period_days > 31:
        return "W"
    return "D"


def clone_without_controls(fig):
    fig2 = go.Figure(fig)
    fig2.update_layout(updatemenus=[], sliders=[])
    return fig2


# ===================== FIGURES =====================

def build_structure_interactive_fig(f_df, t_order):
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

    fig = px.bar(
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

    for stage in WAIT_STAGES:
        stage_df = pd.DataFrame({
            "Компоненты": team_stage_avg["Компоненты"],
            "Дни": team_stage_avg[stage] / 1440
        })

        fig.add_bar(
            x=stage_df["Дни"],
            y=stage_df["Компоненты"],
            name=stage,
            orientation="h",
            marker_color=WAIT_COLORS.get(stage, "#A485E0"),
            text=[f"{x:.1f}" if x > 0 else "" for x in stage_df["Дни"]],
            textposition="auto",
            visible=False
        )

    visible_sum = [True, True] + [False] * len(WAIT_STAGES)
    visible_wait = [False, False] + [True] * len(WAIT_STAGES)

    fig.update_layout(
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
                        args=[{"visible": visible_sum}, {"barmode": "stack"}],
                    ),
                    dict(
                        label="Ожидание",
                        method="update",
                        args=[{"visible": visible_wait}, {"barmode": "stack"}],
                    ),
                ],
            )
        ],
    )
    return fig


def build_structure_sum_fig(f_df, t_order):
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

    fig = px.bar(
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

    fig.update_layout(
        height=270,
        xaxis_title=None,
        yaxis_title=None,
        legend_title=None,
        margin=dict(l=40, r=20, t=10, b=10),
    )
    return fig


def build_structure_wait_fig(f_df, t_order):
    team_stage_avg = f_df.groupby("Компоненты").mean(numeric_only=True).reset_index()
    wait_stage_df = team_stage_avg[["Компоненты"] + WAIT_STAGES].copy()

    for stage in WAIT_STAGES:
        wait_stage_df[stage] = wait_stage_df[stage] / 1440

    wait_long = wait_stage_df.melt(
        id_vars="Компоненты",
        value_vars=WAIT_STAGES,
        var_name="Этап ожидания",
        value_name="Дни"
    )

    fig = px.bar(
        wait_long,
        x="Дни",
        y="Компоненты",
        color="Этап ожидания",
        orientation="h",
        barmode="stack",
        text_auto=".1f",
        category_orders={"Компоненты": t_order},
        color_discrete_map=WAIT_COLORS,
        template="plotly_white",
    )

    fig.update_layout(
        height=270,
        xaxis_title=None,
        yaxis_title=None,
        legend_title=None,
        margin=dict(l=40, r=20, t=10, b=10),
    )
    return fig


def build_load_fig(f_df, t_order):
    t_counts = f_df.groupby("Компоненты").size().reset_index(name="Кол-во")
    fig = px.bar(
        t_counts,
        x="Кол-во",
        y="Компоненты",
        orientation="h",
        text="Кол-во",
        category_orders={"Компоненты": t_order},
        color_discrete_sequence=["#6244BB"],
        template="plotly_white"
    )
    fig.update_layout(
        height=270,
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        margin=dict(l=40, r=20, t=10, b=10)
    )
    return fig


def build_dynamics_fig(f_df, default_granularity="D"):
    daily_df = (
        f_df.set_index("Дата создания")
        .resample("D")
        .size()
        .reset_index(name="Задач")
    )

    weekly_df = (
        f_df.set_index("Дата создания")
        .resample("W")
        .size()
        .reset_index(name="Задач")
    )

    monthly_df = (
        f_df.set_index("Дата создания")
        .resample("ME")
        .size()
        .reset_index(name="Задач")
    )

    weekend_df = daily_df[daily_df["Дата создания"].dt.weekday.isin([5, 6])].copy()

    visible_map = {
        "D": [True, True, False, False],
        "W": [False, False, True, False],
        "M": [False, False, False, True],
    }
    init_visible = visible_map.get(default_granularity, visible_map["D"])

    active_map = {
        "D": 0,
        "W": 1,
        "M": 2,
    }
    active_button = active_map.get(default_granularity, 0)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=daily_df["Дата создания"],
            y=daily_df["Задач"],
            mode="lines+markers",
            name="D",
            visible=init_visible[0],
            line=dict(color="#6244BB"),
            marker=dict(color="#6244BB", size=7),
            hovertemplate="Дата: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=weekend_df["Дата создания"],
            y=weekend_df["Задач"],
            mode="markers",
            name="Выходные",
            visible=init_visible[1],
            marker=dict(
                color="#E45757",
                size=8,
                line=dict(color="white", width=1)
            ),
            hovertemplate="Выходной<br>Дата: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=weekly_df["Дата создания"],
            y=weekly_df["Задач"],
            mode="lines+markers",
            name="W",
            visible=init_visible[2],
            line=dict(color="#6244BB"),
            marker=dict(color="#6244BB", size=7),
            hovertemplate="Неделя до: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=monthly_df["Дата создания"],
            y=monthly_df["Задач"],
            mode="lines+markers",
            name="M",
            visible=init_visible[3],
            line=dict(color="#6244BB"),
            marker=dict(color="#6244BB", size=7),
            hovertemplate="Месяц: %{x|%m.%Y}<br>Задач: %{y}<extra></extra>"
        )
    )

    fig.update_layout(
        height=250,
        xaxis_title=None,
        yaxis_title=None,
        margin=dict(l=20, r=20, t=8, b=10),
        showlegend=False,
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
                active=active_button,
                bgcolor="rgba(243,238,252,1)",
                bordercolor="#E4DDF7",
                borderwidth=1,
                font=dict(size=10, color="#5D4AA8"),
                pad=dict(r=0, t=0),
                buttons=[
                    dict(
                        label="D",
                        method="update",
                        args=[{"visible": [True, True, False, False]}, {"title": None}],
                    ),
                    dict(
                        label="W",
                        method="update",
                        args=[{"visible": [False, False, True, False]}, {"title": None}],
                    ),
                    dict(
                        label="M",
                        method="update",
                        args=[{"visible": [False, False, False, True]}, {"title": None}],
                    ),
                ],
            )
        ],
    )

    return fig


def build_distribution_interactive_fig(f_df):
    dist_df = f_df[["ttm_days", "cycle_time", "wait_time_days"]].dropna().copy()

    fig = go.Figure()

    fig.add_trace(
        go.Histogram(
            x=dist_df["ttm_days"],
            name="TTM",
            marker_color="#6244BB",
            opacity=0.85,
            nbinsx=20,
            visible=True
        )
    )

    fig.add_trace(
        go.Histogram(
            x=dist_df["cycle_time"],
            name="Cycle time",
            marker_color="#6244BB",
            opacity=0.85,
            nbinsx=20,
            visible=False
        )
    )

    fig.add_trace(
        go.Histogram(
            x=dist_df["wait_time_days"],
            name="Ожидание",
            marker_color="#A485E0",
            opacity=0.85,
            nbinsx=20,
            visible=False
        )
    )

    fig.update_layout(
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
                            {"xaxis": {"title": "TTM, дни"}, "yaxis": {"title": "Количество задач"}}
                        ],
                    ),
                    dict(
                        label="Cycle time",
                        method="update",
                        args=[
                            {"visible": [False, True, False]},
                            {"xaxis": {"title": "Cycle time, дни"}, "yaxis": {"title": "Количество задач"}}
                        ],
                    ),
                    dict(
                        label="Ожидание",
                        method="update",
                        args=[
                            {"visible": [False, False, True]},
                            {"xaxis": {"title": "Ожидание, дни"}, "yaxis": {"title": "Количество задач"}}
                        ],
                    ),
                ],
            )
        ],
    )
    return fig


def build_distribution_single_fig(f_df, metric_col, title_label, color):
    dist_df = f_df[[metric_col]].dropna().copy()

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=dist_df[metric_col],
            name=title_label,
            marker_color=color,
            opacity=0.85,
            nbinsx=20
        )
    )

    fig.update_layout(
        height=250,
        xaxis_title=f"{title_label}, дни",
        yaxis_title="Количество задач",
        legend_title=None,
        margin=dict(l=20, r=20, t=20, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        bargap=0.08,
        template="plotly_white",
        showlegend=False,
    )
    return fig


def build_contacts_fig(f_df):
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

    fig = px.pie(
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

    fig.update_traces(textinfo="percent", textfont_size=12)

    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=15, b=15),
        legend_title=None,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=True,
        font=dict(size=11)
    )
    return fig


def build_weekly_count_fig(current_week_df, previous_week_df, team_order_week):
    curr_cnt_team = current_week_df.groupby("Компоненты").size().reset_index(name="Текущая неделя")
    prev_cnt_team = previous_week_df.groupby("Компоненты").size().reset_index(name="Предыдущая неделя")
    cnt_cmp = pd.merge(curr_cnt_team, prev_cnt_team, on="Компоненты", how="outer").fillna(0)

    cnt_long = cnt_cmp.melt(
        id_vars="Компоненты",
        value_vars=["Текущая неделя", "Предыдущая неделя"],
        var_name="Период",
        value_name="Кол-во задач"
    )

    fig = px.bar(
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
    fig.update_layout(
        height=260,
        xaxis_title=None,
        yaxis_title="Кол-во задач",
        legend_title=None,
        margin=dict(l=20, r=20, t=15, b=10)
    )
    return fig


def build_weekly_ttm_interactive_fig(curr_parts, prev_parts):
    fig = go.Figure()

    fig.add_trace(
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

    fig.add_trace(
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

    fig.add_trace(
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

    fig.add_trace(
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

    fig.add_trace(
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

    fig.add_trace(
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

    fig.update_layout(
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
                        args=[{"visible": [True, True, False, False, False, False]}, {"barmode": "group", "yaxis": {"title": "TTM, дней"}}],
                    ),
                    dict(
                        label="Cycle time",
                        method="update",
                        args=[{"visible": [False, False, True, True, False, False]}, {"barmode": "group", "yaxis": {"title": "Cycle time, дней"}}],
                    ),
                    dict(
                        label="Ожидание",
                        method="update",
                        args=[{"visible": [False, False, False, False, True, True]}, {"barmode": "group", "yaxis": {"title": "Ожидание, дней"}}],
                    ),
                ],
            )
        ],
    )
    return fig


def build_weekly_metric_compare_fig(curr_parts, prev_parts, metric_col, curr_name, prev_name, curr_color, prev_color, y_title):
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=curr_parts["Компоненты"],
            y=curr_parts[metric_col],
            name=curr_name,
            marker_color=curr_color,
            text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts[metric_col]],
            textposition="outside",
            cliponaxis=False,
        )
    )

    fig.add_trace(
        go.Bar(
            x=prev_parts["Компоненты"],
            y=prev_parts[metric_col],
            name=prev_name,
            marker_color=prev_color,
            text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts[metric_col]],
            textposition="outside",
            cliponaxis=False,
        )
    )

    fig.update_layout(
        height=260,
        xaxis_title=None,
        yaxis_title=y_title,
        legend_title=None,
        margin=dict(l=20, r=20, t=15, b=10),
        barmode="group",
        template="plotly_white",
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )
    return fig


def build_weekly_flow_fig(current_week_df, previous_week_df, cw_start, cw_end, pw_start, pw_end):
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

    fig = px.line(
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

    fig.update_layout(
        height=220,
        xaxis_title=None,
        yaxis_title="Кол-во задач",
        legend_title=None,
        margin=dict(l=20, r=20, t=15, b=10)
    )
    return fig


def build_weekly_contacts_compare_fig(current_week_df, previous_week_df):
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

    fig = px.bar(
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

    fig.update_layout(
        height=220,
        xaxis_title=None,
        yaxis_title="Кол-во задач",
        legend_title=None,
        margin=dict(l=20, r=20, t=15, b=10)
    )
    return fig


# ===================== PDF EXPORT =====================

PDF_BG = HexColor("#F7F2FA")
PDF_CARD = HexColor("#FFFFFF")
PDF_BORDER = HexColor("#E6E9EF")
PDF_ACCENT = HexColor("#6244BB")
PDF_TEXT = HexColor("#1A1C1E")
PDF_SUB = HexColor("#7E8694")


def truncate_text(text, max_len=140):
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def format_filter_line(label, values, max_len=150):
    if not values:
        return f"{label}: все"
    txt = ", ".join(map(str, values))
    return truncate_text(f"{label}: {txt}", max_len=max_len)


def fig_to_png_bytes(fig, width_px=1200, height_px=700, scale=2):
    fig2 = clone_without_controls(fig)
    fig2.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    try:
        return fig2.to_image(format="png", width=width_px, height=height_px, scale=scale)
    except Exception as e:
        raise RuntimeError(
            "Не удалось собрать PDF-экспорт. Для экспорта нужны установленные зависимости kaleido и reportlab."
        ) from e


def draw_round_rect(c, x, y, w, h, fill_color=PDF_CARD, stroke_color=PDF_BORDER, radius=14, stroke_width=1):
    c.setFillColor(fill_color)
    c.setStrokeColor(stroke_color)
    c.setLineWidth(stroke_width)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def draw_page_header(c, page_w, page_h, title, subtitle_lines, page_num, total_pages):
    margin = 24
    y_top = page_h - margin

    c.setFillColor(PDF_BG)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    c.setFillColor(PDF_TEXT)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, y_top - 8, title)

    c.setFillColor(PDF_SUB)
    c.setFont("Helvetica", 9)
    line_y = y_top - 24
    for line in subtitle_lines:
        c.drawString(margin, line_y, line)
        line_y -= 11

    c.setFillColor(PDF_ACCENT)
    c.roundRect(page_w - margin - 64, y_top - 22, 64, 18, 8, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(page_w - margin - 32, y_top - 9, f"{page_num}/{total_pages}")

    c.setStrokeColor(HexColor("#D8CDF4"))
    c.setLineWidth(1)
    c.line(margin, y_top - 42, page_w - margin, y_top - 42)

    return y_top - 54


def draw_kpi_row_pdf(c, page_w, y_top, cards):
    margin = 24
    gap = 8
    n = len(cards)
    usable_w = page_w - 2 * margin
    card_w = (usable_w - gap * (n - 1)) / n
    card_h = 84
    y = y_top - card_h

    for i, card in enumerate(cards):
        x = margin + i * (card_w + gap)
        draw_round_rect(c, x, y, card_w, card_h, fill_color=PDF_CARD, stroke_color=PDF_BORDER, radius=12)

        c.setFillColor(PDF_TEXT)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 10, y + card_h - 16, truncate_text(card["title"], 24))

        c.setFillColor(HexColor(card.get("color", "#6244BB")))
        c.setFont("Helvetica-Bold", 17)
        c.drawString(x + 10, y + card_h - 40, str(card["value"]))

        if card.get("subvalue"):
            c.setFillColor(PDF_SUB)
            c.setFont("Helvetica", 8)
            c.drawString(x + 10, y + 10, truncate_text(card["subvalue"], 26))

    return y - 12


def draw_chart_panel(c, x, y, w, h, title, fig):
    draw_round_rect(c, x, y, w, h, fill_color=PDF_CARD, stroke_color=PDF_BORDER, radius=14)

    c.setFillColor(PDF_TEXT)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 12, y + h - 16, truncate_text(title, 60))

    img_pad_x = 10
    img_pad_bottom = 10
    header_h = 28

    img_w = w - 2 * img_pad_x
    img_h = h - header_h - img_pad_bottom - 4

    png = fig_to_png_bytes(
        fig,
        width_px=max(1000, int(img_w * 2)),
        height_px=max(650, int(img_h * 2)),
        scale=2
    )
    reader = ImageReader(io.BytesIO(png))
    c.drawImage(
        reader,
        x + img_pad_x,
        y + img_pad_bottom,
        width=img_w,
        height=img_h,
        preserveAspectRatio=False,
        mask="auto"
    )


def build_overview_export_pdf(
    f_df,
    start_date,
    end_date,
    sel_teams,
    sel_res,
    sel_types,
    default_granularity,
):
    buffer = io.BytesIO()
    page_w, page_h = landscape(A3)
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    margin = 24
    gap = 12
    content_w = page_w - 2 * margin

    time_order_df = (
        f_df.groupby("Компоненты")["ttm_days"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    t_order = time_order_df["Компоненты"].tolist()

    fig_structure_sum = build_structure_sum_fig(f_df, t_order)
    fig_structure_wait = build_structure_wait_fig(f_df, t_order)
    fig_load = build_load_fig(f_df, t_order)
    fig_dynamics = clone_without_controls(build_dynamics_fig(f_df, default_granularity=default_granularity))
    fig_dist_ttm = build_distribution_single_fig(f_df, "ttm_days", "TTM", "#6244BB")
    fig_dist_cycle = build_distribution_single_fig(f_df, "cycle_time", "Cycle time", "#6244BB")
    fig_dist_wait = build_distribution_single_fig(f_df, "wait_time_days", "Ожидание", "#A485E0")
    fig_contacts = build_contacts_fig(f_df)

    avg_ttm = f_df["ttm_days"].mean() if len(f_df) else 0.0
    med_ttm = f_df["ttm_days"].median() if len(f_df) else 0.0
    avg_cycle = f_df["cycle_time"].mean() if len(f_df) else 0.0
    med_cycle = f_df["cycle_time"].median() if len(f_df) else 0.0
    avg_wait = f_df["wait_time_days"].mean() if len(f_df) else 0.0
    med_wait = f_df["wait_time_days"].median() if len(f_df) else 0.0
    late = ((f_df["Резолюция"] == "Позже").mean() * 100) if len(f_df) else 0.0
    active = (f_df["cycle_time"].sum() / f_df["ttm_days"].sum() * 100) if f_df["ttm_days"].sum() > 0 else 0.0
    pingpong_share = ((f_df["Пинг-понг обращения"] > 1).mean() * 100) if len(f_df) else 0.0
    tasks_with_pingpong = (f_df["Пинг-понг обращения"] > 1).sum() if len(f_df) else 0

    subtitle_lines = [
        f"Период анализа: {pd.to_datetime(start_date).strftime('%d.%m.%Y')} - {pd.to_datetime(end_date).strftime('%d.%m.%Y')}",
        format_filter_line("Команды", sel_teams),
        format_filter_line("Резолюции", sel_res),
        format_filter_line("Тип", sel_types),
    ]

    cards = [
        {"title": "Всего задач", "value": f"{len(f_df)}", "subvalue": "", "color": "#6244BB"},
        {"title": "TTM (дн)", "value": f"{avg_ttm:.2f}", "subvalue": f"медиана: {med_ttm:.2f}", "color": "#6244BB"},
        {"title": "Cycle time (дн)", "value": f"{avg_cycle:.2f}", "subvalue": f"медиана: {med_cycle:.2f}", "color": "#6244BB"},
        {"title": "Ожидание (дн)", "value": f"{avg_wait:.2f}", "subvalue": f"медиана: {med_wait:.2f}", "color": "#6244BB"},
        {"title": "Позже", "value": f"{late:.1f}%", "subvalue": "", "color": "#E45757" if late > 50 else "#4CAF7D"},
        {"title": "Flow Efficiency", "value": f"{active:.0f}%", "subvalue": "", "color": "#E45757" if active < 50 else "#4CAF7D"},
        {"title": "Пинг-понг > 1", "value": f"{pingpong_share:.1f}%", "subvalue": f"задач: {tasks_with_pingpong}", "color": "#E45757" if pingpong_share > 20 else "#4CAF7D"},
    ]

    # PAGE 1
    y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Общий обзор", subtitle_lines, 1, 2)
    y_cursor = draw_kpi_row_pdf(c, page_w, y_cursor, cards)

    col_w = (content_w - gap) / 2
    row_h = 285

    draw_chart_panel(c, margin, y_cursor - row_h, col_w, row_h, "Структура времени задач по командам - суммарно", fig_structure_sum)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h, col_w, row_h, "Нагрузка по командам", fig_load)

    y_cursor = y_cursor - row_h - gap
    draw_chart_panel(c, margin, y_cursor - row_h, col_w, row_h, "Структура времени задач по командам - ожидание", fig_structure_wait)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h, col_w, row_h, "Динамика поступления задач", fig_dynamics)

    c.showPage()

    # PAGE 2
    y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Общий обзор (продолжение)", subtitle_lines, 2, 2)

    row_h2 = 320
    draw_chart_panel(c, margin, y_cursor - row_h2, col_w, row_h2, "Распределение времени задач - TTM", fig_dist_ttm)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h2, col_w, row_h2, "Распределение времени задач - Cycle time", fig_dist_cycle)

    y_cursor = y_cursor - row_h2 - gap
    draw_chart_panel(c, margin, y_cursor - row_h2, col_w, row_h2, "Распределение времени задач - ожидание", fig_dist_wait)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h2, col_w, row_h2, "Структура обращений", fig_contacts)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def build_weekly_export_pdf(
    current_week_df,
    previous_week_df,
    current_metrics,
    previous_metrics,
    cw_start,
    cw_end,
    pw_start,
    pw_end,
    sel_teams,
    sel_res,
    sel_types,
):
    buffer = io.BytesIO()
    page_w, page_h = landscape(A3)
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    margin = 24
    gap = 12
    content_w = page_w - 2 * margin

    subtitle_lines = [
        f"Текущая неделя: {cw_start.strftime('%d.%m.%Y')} - {cw_end.strftime('%d.%m.%Y')}",
        f"Предыдущая неделя: {pw_start.strftime('%d.%m.%Y')} - {pw_end.strftime('%d.%m.%Y')}",
        format_filter_line("Команды", sel_teams),
        format_filter_line("Резолюции", sel_res),
        format_filter_line("Тип", sel_types),
    ]

    cards = [
        {
            "title": "Всего задач",
            "value": format_value(current_metrics["tasks_total"], as_int=True),
            "subvalue": f"пред.: {format_value(previous_metrics['tasks_total'], as_int=True)}",
            "color": "#6244BB",
        },
        {
            "title": "TTM (дн)",
            "value": format_value(current_metrics["ttm"]),
            "subvalue": f"∆ {delta_text(current_metrics['ttm'], previous_metrics['ttm'])}",
            "color": "#6244BB",
        },
        {
            "title": "Cycle time (дн)",
            "value": format_value(current_metrics["cycle"]),
            "subvalue": f"∆ {delta_text(current_metrics['cycle'], previous_metrics['cycle'])}",
            "color": "#6244BB",
        },
        {
            "title": "Ожидание (дн)",
            "value": format_value(current_metrics["wait"]),
            "subvalue": f"∆ {delta_text(current_metrics['wait'], previous_metrics['wait'])}",
            "color": "#6244BB",
        },
        {
            "title": "Позже",
            "value": format_value(current_metrics["later_pct"], is_percent=True),
            "subvalue": f"∆ {delta_text(current_metrics['later_pct'], previous_metrics['later_pct'], is_percent=True)}",
            "color": "#6244BB",
        },
        {
            "title": "Flow Efficiency",
            "value": format_value(current_metrics["active_pct"], is_percent=True),
            "subvalue": f"∆ {delta_text(current_metrics['active_pct'], previous_metrics['active_pct'], is_percent=True)}",
            "color": "#6244BB",
        },
        {
            "title": "Пинг-понг > 1",
            "value": format_value(current_metrics["pingpong_share"], is_percent=True),
            "subvalue": f"∆ {delta_text(current_metrics['pingpong_share'], previous_metrics['pingpong_share'], is_percent=True)}",
            "color": "#6244BB",
        },
    ]

    if current_week_df.empty or previous_week_df.empty:
        y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Сравнение недель", subtitle_lines, 1, 1)
        draw_kpi_row_pdf(c, page_w, y_cursor, cards)
        c.setFillColor(PDF_TEXT)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, page_h / 2, "Недостаточно данных для сравнения текущей и предыдущей недели.")
        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    team_order_week = (
        pd.concat([current_week_df["Компоненты"], previous_week_df["Компоненты"]])
        .dropna()
        .value_counts()
        .index
        .tolist()
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

    fig_cnt_compare = build_weekly_count_fig(current_week_df, previous_week_df, team_order_week)
    fig_ttm_only = build_weekly_metric_compare_fig(
        curr_parts, prev_parts,
        "ttm_days",
        "TTM — текущая",
        "TTM — предыдущая",
        "#6244BB",
        "#D6CCFF",
        "TTM, дней"
    )
    fig_cycle_only = build_weekly_metric_compare_fig(
        curr_parts, prev_parts,
        "cycle_time",
        "Cycle time — текущая",
        "Cycle time — предыдущая",
        "#6244BB",
        "#D6CCFF",
        "Cycle time, дней"
    )
    fig_wait_only = build_weekly_metric_compare_fig(
        curr_parts, prev_parts,
        "wait_time_days",
        "Ожидание — текущая",
        "Ожидание — предыдущая",
        "#A485E0",
        "#EEE8FF",
        "Ожидание, дней"
    )
    fig_flow = build_weekly_flow_fig(current_week_df, previous_week_df, cw_start, cw_end, pw_start, pw_end)
    fig_contacts_compare = build_weekly_contacts_compare_fig(current_week_df, previous_week_df)

    # PAGE 1
    y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Сравнение недель", subtitle_lines, 1, 2)
    y_cursor = draw_kpi_row_pdf(c, page_w, y_cursor, cards)

    col_w = (content_w - gap) / 2
    row_h = 285

    draw_chart_panel(c, margin, y_cursor - row_h, col_w, row_h, "Количество задач", fig_cnt_compare)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h, col_w, row_h, "TTM по командам", fig_ttm_only)

    y_cursor = y_cursor - row_h - gap
    draw_chart_panel(c, margin, y_cursor - row_h, col_w, row_h, "Cycle time по командам", fig_cycle_only)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h, col_w, row_h, "Ожидание по командам", fig_wait_only)

    c.showPage()

    # PAGE 2
    y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Сравнение недель (продолжение)", subtitle_lines, 2, 2)
    row_h2 = 340

    draw_chart_panel(c, margin, y_cursor - row_h2, col_w, row_h2, "Поступление задач", fig_flow)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h2, col_w, row_h2, "Количество обращений", fig_contacts_compare)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


@st.cache_data(show_spinner="Готовлю PDF-экспорт...")
def build_export_pdf_cached(
    active_view_name,
    f_df,
    current_week_df,
    previous_week_df,
    current_metrics,
    previous_metrics,
    start_date,
    end_date,
    sel_teams,
    sel_res,
    sel_types,
    default_granularity,
    cw_start,
    cw_end,
    pw_start,
    pw_end,
):
    if active_view_name == "Общий обзор":
        return build_overview_export_pdf(
            f_df=f_df,
            start_date=start_date,
            end_date=end_date,
            sel_teams=sel_teams,
            sel_res=sel_res,
            sel_types=sel_types,
            default_granularity=default_granularity,
        )

    return build_weekly_export_pdf(
        current_week_df=current_week_df,
        previous_week_df=previous_week_df,
        current_metrics=current_metrics,
        previous_metrics=previous_metrics,
        cw_start=cw_start,
        cw_end=cw_end,
        pw_start=pw_start,
        pw_end=pw_end,
        sel_teams=sel_teams,
        sel_res=sel_res,
        sel_types=sel_types,
    )


# ===================== TOP BAR =====================

if "show_upload_block" not in st.session_state:
    st.session_state["show_upload_block"] = False

if "data" not in st.session_state:
    db_df = read_dashboard_from_postgres(POSTGRES_URL)
    if not db_df.empty:
        st.session_state["data"] = db_df

if "active_view" not in st.session_state:
    st.session_state["active_view"] = "Общий обзор"

df = st.session_state.get("data", pd.DataFrame())

if df.empty:
    st.warning("После обработки данные пустые.")
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

period_days = get_period_days(start_date, end_date)
default_granularity = get_default_granularity(period_days)

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

# ===================== WEEKLY COMPARISON =====================

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

# ===================== TOP BAR =====================

@st.fragment
def top_bar_fragment(export_bytes=None, export_filename="dashboard_export.pdf", export_error=None):
    title_col, import_col, export_col = st.columns([8, 1, 1])

    with title_col:
        st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

    with import_col:
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        if st.button("Импорт", key="toggle_upload_btn"):
            st.session_state["show_upload_block"] = not st.session_state["show_upload_block"]

    with export_col:
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        if export_error:
            st.caption("Экспорт недоступен")
        elif export_bytes is not None:
            st.download_button(
                "Экспорт",
                data=export_bytes,
                file_name=export_filename,
                mime="application/pdf",
                key="export_dashboard_pdf_btn",
            )

    if st.session_state["show_upload_block"]:
        st.info(
            "Загрузите 2 файла CSV или XLSX. После загрузки данные автоматически объединятся, "
            "очистятся, сохранятся в базу и дашборд обновится."
        )

        uploaded_files = st.file_uploader(
            "Загрузите 2 файла",
            type=["csv", "xlsx"],
            accept_multiple_files=True,
            key="uploaded_files_main"
        )

        if uploaded_files and len(uploaded_files) != 2:
            st.warning("Пожалуйста, загрузите ровно 2 файла.")

        if st.button("Обработать файлы", key="process_files_btn"):
            if not uploaded_files or len(uploaded_files) != 2:
                st.error("Нужно загрузить ровно 2 файла.")
            else:
                try:
                    df_left = load_single_file(uploaded_files[0], uploaded_files[0].name)
                    df_right = load_single_file(uploaded_files[1], uploaded_files[1].name)

                    prepared_merge = load_and_prepare_two_dataframes(df_left, df_right)
                    prepared_df = prepare_dashboard_data(prepared_merge)

                    inserted_rows = write_dashboard_to_postgres_append(
                        prepared_df,
                        postgres_url=POSTGRES_URL,
                        source="manual_upload",
                        file_names=f"{uploaded_files[0].name} | {uploaded_files[1].name}",
                    )

                    db_df = read_dashboard_from_postgres(POSTGRES_URL)
                    st.session_state["data"] = db_df if not db_df.empty else prepared_df

                    st.success(f"Файлы успешно загружены. В базу добавлено новых строк: {inserted_rows}")
                    st.rerun()

                except Exception as e:
                    st.error(str(e))


if not weekly_ready and st.session_state["active_view"] == "Сравнение недель":
    export_filename = f"dashboard_weekly_{pd.to_datetime(start_date).strftime('%Y%m%d')}_{pd.to_datetime(end_date).strftime('%Y%m%d')}.pdf"
else:
    export_filename = f"dashboard_{pd.to_datetime(start_date).strftime('%Y%m%d')}_{pd.to_datetime(end_date).strftime('%Y%m%d')}.pdf"

export_error = None
export_bytes = None

try:
    export_bytes = build_export_pdf_cached(
        active_view_name=st.session_state.get("active_view", "Общий обзор"),
        f_df=f_df,
        current_week_df=current_week_df,
        previous_week_df=previous_week_df,
        current_metrics=current_metrics,
        previous_metrics=previous_metrics,
        start_date=str(start_date),
        end_date=str(end_date),
        sel_teams=sel_teams,
        sel_res=sel_res,
        sel_types=sel_types,
        default_granularity=default_granularity,
        cw_start=cw_start,
        cw_end=cw_end,
        pw_start=pw_start,
        pw_end=pw_end,
    )
except Exception as e:
    export_error = str(e)

top_bar_fragment(
    export_bytes=export_bytes,
    export_filename=export_filename,
    export_error=export_error
)

meta_df = read_meta_from_postgres(POSTGRES_URL)
if not meta_df.empty:
    last_meta = meta_df.iloc[0]
    st.caption(
        f"Последнее обновление: {last_meta['updated_at']} | "
        f"Источник: {last_meta['source']} | "
        f"Строк в данных: {last_meta['rows_count_in_batch']} | "
        f"Добавлено новых строк: {last_meta['inserted_rows']}"
    )

# ===================== VIEW SWITCHER =====================

st.radio(
    "Раздел",
    ["Общий обзор", "Сравнение недель"],
    horizontal=True,
    key="active_view",
    label_visibility="collapsed"
)


def render_overview():
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7, gap="small")

    with k1:
        kpi_card("Всего задач", f"{len(f_df)}", "Общее число задач за выбранный период, которые поступили в работу")

    with k2:
        med = f_df["ttm_days"].median() if len(f_df) else 0.0
        avg = f_df["ttm_days"].mean() if len(f_df) else 0.0
        kpi_card(
            "TTM (дн)",
            f"{avg:.2f}",
            "Сколько в среднем времени занимал путь задач по процессу целиком, считается в днях. Так же тут указана медиана, она показывает более типичное значение",
            subvalue=f"медиана: {med:.2f}"
        )

    with k3:
        med = f_df["cycle_time"].median() if len(f_df) else 0.0
        avg = f_df["cycle_time"].mean() if len(f_df) else 0.0
        kpi_card(
            "Cycle time (дн)",
            f"{avg:.2f}",
            "Среднее время активной работы над задачами, считается в днях. Также тут указана медиана, она показывает более типичное значение",
            subvalue=f"медиана: {med:.2f}"
        )

    with k4:
        avg = f_df["wait_time_days"].mean() if len(f_df) else 0.0
        med = f_df["wait_time_days"].median() if len(f_df) else 0.0
        kpi_card(
            "Ожидание (дн)",
            f"{avg:.2f}",
            "Среднее время, которое задача проводила вне активной работы. Среднее ожидание = среднее значение разницы между TTM и Cycle time",
            subvalue=f"медиана: {med:.2f}"
        )

    with k5:
        late = ((f_df["Резолюция"] == "Позже").mean() * 100) if len(f_df) else 0
        late_color = "#E45757" if late > 50 else "#4CAF7D"
        kpi_card("Позже", f"{late:.1f}%", "Доля задач, которые решены позже", color=late_color)

    with k6:
        active = (
            (f_df["cycle_time"].sum() / f_df["ttm_days"].sum()) * 100
            if f_df["ttm_days"].sum() > 0 else 0
        )
        active_color = "#E45757" if active < 50 else "#4CAF7D"
        kpi_card(
            "Flow Efficiency",
            f"{active:.0f}%",
            "Доля активной работы в общем времени работы над задачей, то есть cycle time / TTM",
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
            "Доля задач, которые передавались между командами более одного раза, если была только одна команда, то стоит 1",
            subvalue=f"задач: {tasks_with_pingpong}",
            color=pingpong_color,
            hint_side="left"
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    time_order_df = (
        f_df.groupby("Компоненты")["ttm_days"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    t_order = time_order_df["Компоненты"].tolist()

    fig_structure_interactive = build_structure_interactive_fig(f_df, t_order)
    fig_load = build_load_fig(f_df, t_order)
    fig_dynamics = build_dynamics_fig(f_df, default_granularity=default_granularity)
    fig_dist_interactive = build_distribution_interactive_fig(f_df)
    fig_contacts = build_contacts_fig(f_df)

    c1, c2 = st.columns(2, gap="small")

    with c1:
        st.markdown(
            f'<div class="card-header">Структура времени задач по командам</div>'
            f'<span class="hint-icon" data-hint="Можно посмотреть суммарно Cycle time + ожидание или только этапы ожидания">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_structure_interactive,
            use_container_width=True,
            config={"displayModeBar": False}
        )

    with c2:
        st.markdown(
            f'<div class="card-header">Нагрузка по командам</div>'
            f'<span class="hint-icon" data-hint="Количество задач, которые были взяты в работу по командам">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_load,
            use_container_width=True,
            config={"displayModeBar": False}
        )

    b1, b2, b3 = st.columns(3, gap="small")

    with b1:
        st.markdown(
            f'<div class="card-header">Динамика поступления задач</div>'
            f'<span class="hint-icon" data-hint="Количество новых задач по дням, неделям или месяцам">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_dynamics,
            use_container_width=True,
            config={"displayModeBar": False, "scrollZoom": False}
        )

    with b2:
        st.markdown(
            f'<div class="card-header">Распределение времени задач</div>'
            f'<span class="hint-icon" data-hint="Можно посмотреть распределение TTM, Cycle time или ожидания по задачам">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_dist_interactive,
            use_container_width=True,
            config={"displayModeBar": False, "scrollZoom": False}
        )

    with b3:
        st.markdown(
            f'<div class="card-header">Структура обращений</div>'
            f'<span class="hint-icon" data-hint="Распределение задач по категориям количества обращений">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_contacts,
            use_container_width=True,
            config={"displayModeBar": False, "scrollZoom": False}
        )


def render_weekly():
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
        return

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
            "TTM (дн)",
            current_metrics["ttm"],
            previous_metrics["ttm"],
            hint="Среднее время от открытия задачи до её закрытия за текущую неделю"
        )
    with w3:
        kpi_compare_card(
            "Cycle time (дн)",
            current_metrics["cycle"],
            previous_metrics["cycle"],
            hint="Среднее время активной работы над задачей за текущую неделю"
        )
    with w4:
        kpi_compare_card(
            "Ожидание (дн)",
            current_metrics["wait"],
            previous_metrics["wait"],
            hint="Среднее время ожидания за текущую неделю"
        )
    with w5:
        kpi_compare_card(
            "Позже",
            current_metrics["later_pct"],
            previous_metrics["later_pct"],
            hint="Доля задач с резолюцией 'Позже'",
            is_percent=True
        )
    with w6:
        kpi_compare_card(
            "Flow Efficiency",
            current_metrics["active_pct"],
            previous_metrics["active_pct"],
            hint="Доля активной работы в общем времени",
            is_percent=True
        )
    with w7:
        kpi_compare_card(
            "Пинг-понг > 1",
            current_metrics["pingpong_share"],
            previous_metrics["pingpong_share"],
            hint="Доля задач, которые передавались между командами более одного раза",
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

    fig_cnt_compare = build_weekly_count_fig(current_week_df, previous_week_df, team_order_week)
    fig_ttm_interactive = build_weekly_ttm_interactive_fig(curr_parts, prev_parts)
    fig_flow = build_weekly_flow_fig(current_week_df, previous_week_df, cw_start, cw_end, pw_start, pw_end)
    fig_contacts_compare = build_weekly_contacts_compare_fig(current_week_df, previous_week_df)

    g1, g2 = st.columns(2, gap="small")

    with g1:
        st.markdown(
            f'<div class="card-header">Количество задач</div>'
            f'<span class="hint-icon" data-hint="Сравнение объёма задач по командам за две недели">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_cnt_compare,
            use_container_width=True,
            config={"displayModeBar": False}
        )

    with g2:
        st.markdown(
            f'<div class="card-header">TTM по командам</div>'
            f'<span class="hint-icon" data-hint="Можно посмотреть TTM, Cycle time или ожидание по командам за две недели">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_ttm_interactive,
            use_container_width=True,
            config={"displayModeBar": False}
        )

    g3, g4 = st.columns(2, gap="small")

    with g3:
        st.markdown(
            f'<div class="card-header">Поступление задач</div>'
            f'<span class="hint-icon" data-hint="Сравнение количества новых задач по дням для текущей недели и предыдущей">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_flow,
            use_container_width=True,
            config={"displayModeBar": False}
        )

    with g4:
        st.markdown(
            f'<div class="card-header">Количество обращений</div>'
            f'<span class="hint-icon" data-hint="Сравнение категорий количества обращений за две недели">?</span>',
            unsafe_allow_html=True
        )
        st.plotly_chart(
            fig_contacts_compare,
            use_container_width=True,
            config={"displayModeBar": False}
        )


# ===================== UI =====================

if st.session_state["active_view"] == "Общий обзор":
    render_overview()
else:
    render_weekly()
