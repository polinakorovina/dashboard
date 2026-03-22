import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta, date

from data_pipeline import read_dashboard_from_postgres, read_meta_from_postgres
from import_utils import process_uploaded_files
from export_utils import build_overview_export_pdf, build_weekly_export_pdf


st.set_page_config(page_title="Аналитика дежурств", layout="wide")

ACCESS_TOKEN = st.secrets["ACCESS_TOKEN"]
POSTGRES_URL = st.secrets["POSTGRES_URL"]

token = st.query_params.get("token")
if token != ACCESS_TOKEN:
    st.markdown("## Доступ ограничен")
    st.error("Эта ссылка недействительна или у вас нет доступа.")
    st.stop()


def init_session_state():
    if "show_upload_block" not in st.session_state:
        st.session_state["show_upload_block"] = False

    if "active_view" not in st.session_state:
        st.session_state["active_view"] = "Общий обзор"

    if "data_version" not in st.session_state:
        st.session_state["data_version"] = 0

    if "overview_bundle_cache" not in st.session_state:
        st.session_state["overview_bundle_cache"] = {}

    if "weekly_bundle_cache" not in st.session_state:
        st.session_state["weekly_bundle_cache"] = {}

    if "data" not in st.session_state:
        st.session_state["data"] = pd.DataFrame()


init_session_state()

TTM_STAGES = [
    "Сбор данных",
    "Открыт",
    "Заблокирован",
    "На стороне менеджера",
    "Бэклог разработки",
    "В работе",
]
CYCLE_STAGES = ["Бэклог разработки", "В работе"]
WAIT_STAGES = [stage for stage in TTM_STAGES if stage not in CYCLE_STAGES]

WAIT_COLORS = {
    "Сбор данных": "#5B3FC4",
    "Открыт": "#8A6BE8",
    "Заблокирован": "#B59AF5",
    "На стороне менеджера": "#E3D9FF",
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
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, show_spinner=False)
def read_dashboard_cached(postgres_url: str) -> pd.DataFrame:
    return read_dashboard_from_postgres(postgres_url)


@st.cache_data(ttl=300, show_spinner=False)
def read_meta_cached(postgres_url: str) -> pd.DataFrame:
    return read_meta_from_postgres(postgres_url)


if st.session_state["data"].empty:
    db_df = read_dashboard_cached(POSTGRES_URL)
    st.session_state["data"] = db_df if not db_df.empty else pd.DataFrame()


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
        unsafe_allow_html=True,
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
        unsafe_allow_html=True,
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
            "pingpong_share": 0.0,
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
        "pingpong_share": pingpong_share,
    }


def get_period_days(start_date, end_date):
    return (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1


def get_default_granularity(period_days: int):
    if period_days > 183:
        return "M"
    if period_days > 31:
        return "W"
    return "D"


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
        value_name="Дни",
    )

    name_map = {"cycle_time": "Cycle time", "wait_time_days": "Ожидание"}
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
        color_discrete_map={"Cycle time": "#6244BB", "Ожидание": "#A485E0"},
        template="plotly_white",
    )

    for stage in WAIT_STAGES:
        stage_df = pd.DataFrame({
            "Компоненты": team_stage_avg["Компоненты"],
            "Дни": team_stage_avg[stage] / 1440,
        })

        fig.add_bar(
            x=stage_df["Дни"],
            y=stage_df["Компоненты"],
            name=stage,
            orientation="h",
            marker_color=WAIT_COLORS.get(stage, "#A485E0"),
            text=[f"{x:.1f}" if x > 0 else "" for x in stage_df["Дни"]],
            textposition="auto",
            visible=False,
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
                    dict(label="Суммарно", method="update", args=[{"visible": visible_sum}, {"barmode": "stack"}]),
                    dict(label="Ожидание", method="update", args=[{"visible": visible_wait}, {"barmode": "stack"}]),
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
        value_name="Дни",
    )

    name_map = {"cycle_time": "Cycle time", "wait_time_days": "Ожидание"}
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
        color_discrete_map={"Cycle time": "#6244BB", "Ожидание": "#A485E0"},
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
        value_name="Дни",
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
        template="plotly_white",
    )
    fig.update_layout(
        height=270,
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        margin=dict(l=40, r=20, t=10, b=10),
    )
    return fig


def build_dynamics_fig(f_df, default_granularity="D"):
    daily_df = f_df.set_index("Дата создания").resample("D").size().reset_index(name="Задач")
    weekly_df = f_df.set_index("Дата создания").resample("W").size().reset_index(name="Задач")
    monthly_df = f_df.set_index("Дата создания").resample("ME").size().reset_index(name="Задач")

    weekend_df = daily_df[daily_df["Дата создания"].dt.weekday.isin([5, 6])].copy()

    visible_map = {"D": [True, True, False, False], "W": [False, False, True, False], "M": [False, False, False, True]}
    init_visible = visible_map.get(default_granularity, visible_map["D"])
    active_map = {"D": 0, "W": 1, "M": 2}
    active_button = active_map.get(default_granularity, 0)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=daily_df["Дата создания"],
        y=daily_df["Задач"],
        mode="lines+markers",
        name="D",
        visible=init_visible[0],
        line=dict(color="#6244BB"),
        marker=dict(color="#6244BB", size=7),
        hovertemplate="Дата: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=weekend_df["Дата создания"],
        y=weekend_df["Задач"],
        mode="markers",
        name="Выходные",
        visible=init_visible[1],
        marker=dict(color="#E45757", size=8, line=dict(color="white", width=1)),
        hovertemplate="Выходной<br>Дата: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=weekly_df["Дата создания"],
        y=weekly_df["Задач"],
        mode="lines+markers",
        name="W",
        visible=init_visible[2],
        line=dict(color="#6244BB"),
        marker=dict(color="#6244BB", size=7),
        hovertemplate="Неделя до: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=monthly_df["Дата создания"],
        y=monthly_df["Задач"],
        mode="lines+markers",
        name="M",
        visible=init_visible[3],
        line=dict(color="#6244BB"),
        marker=dict(color="#6244BB", size=7),
        hovertemplate="Месяц: %{x|%m.%Y}<br>Задач: %{y}<extra></extra>",
    ))

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
                    dict(label="D", method="update", args=[{"visible": [True, True, False, False]}, {"title": None}]),
                    dict(label="W", method="update", args=[{"visible": [False, False, True, False]}, {"title": None}]),
                    dict(label="M", method="update", args=[{"visible": [False, False, False, True]}, {"title": None}]),
                ],
            )
        ],
    )
    return fig


def build_distribution_interactive_fig(f_df):
    dist_df = f_df[["ttm_days", "cycle_time", "wait_time_days"]].dropna().copy()

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=dist_df["ttm_days"], name="TTM", marker_color="#6244BB", opacity=0.85, nbinsx=20, visible=True))
    fig.add_trace(go.Histogram(x=dist_df["cycle_time"], name="Cycle time", marker_color="#6244BB", opacity=0.85, nbinsx=20, visible=False))
    fig.add_trace(go.Histogram(x=dist_df["wait_time_days"], name="Ожидание", marker_color="#A485E0", opacity=0.85, nbinsx=20, visible=False))

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
                    dict(label="TTM", method="update", args=[{"visible": [True, False, False]}, {"xaxis": {"title": "TTM, дни"}, "yaxis": {"title": "Количество задач"}}]),
                    dict(label="Cycle time", method="update", args=[{"visible": [False, True, False]}, {"xaxis": {"title": "Cycle time, дни"}, "yaxis": {"title": "Количество задач"}}]),
                    dict(label="Ожидание", method="update", args=[{"visible": [False, False, True]}, {"xaxis": {"title": "Ожидание, дни"}, "yaxis": {"title": "Количество задач"}}]),
                ],
            )
        ],
    )
    return fig


def build_distribution_single_fig(f_df, metric_col, title_label, color):
    dist_df = f_df[[metric_col]].dropna().copy()

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=dist_df[metric_col], name=title_label, marker_color=color, opacity=0.85, nbinsx=20))

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
    contacts_dist = f_df["Количество обращений"].value_counts(dropna=False).reset_index()
    contacts_dist.columns = ["Количество обращений", "Кол-во"]

    cat_order = ["1-4", "5-10", "11-100", "100+"]
    contacts_dist["Количество обращений"] = pd.Categorical(
        contacts_dist["Количество обращений"],
        categories=cat_order,
        ordered=True,
    )
    contacts_dist = contacts_dist.sort_values("Количество обращений")

    fig = px.pie(
        contacts_dist,
        names="Количество обращений",
        values="Кол-во",
        hole=0.6,
        color="Количество обращений",
        color_discrete_map={"1-4": "#5B3FC4", "5-10": "#8C6FF0", "11-100": "#B9A3FA", "100+": "#E1D8FF"},
        template="plotly_white",
    )

    fig.update_traces(textinfo="percent", textfont_size=12)
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=15, b=15),
        legend_title=None,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=True,
        font=dict(size=11),
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
        value_name="Кол-во задач",
    )

    fig = px.bar(
        cnt_long,
        x="Компоненты",
        y="Кол-во задач",
        color="Период",
        barmode="group",
        text_auto=".0f",
        category_orders={"Компоненты": team_order_week},
        color_discrete_map={"Текущая неделя": "#6244BB", "Предыдущая неделя": "#D6CCFF"},
        template="plotly_white",
    )
    fig.update_layout(
        height=260,
        xaxis_title=None,
        yaxis_title="Кол-во задач",
        legend_title=None,
        margin=dict(l=20, r=20, t=15, b=10),
    )
    return fig


def build_weekly_ttm_interactive_fig(curr_parts, prev_parts):
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=curr_parts["Компоненты"], y=curr_parts["ttm_days"], name="TTM — текущая",
        marker_color="#6244BB",
        text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["ttm_days"]],
        textposition="outside", cliponaxis=False, visible=True
    ))
    fig.add_trace(go.Bar(
        x=prev_parts["Компоненты"], y=prev_parts["ttm_days"], name="TTM — предыдущая",
        marker_color="#D6CCFF",
        text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["ttm_days"]],
        textposition="outside", cliponaxis=False, visible=True
    ))
    fig.add_trace(go.Bar(
        x=curr_parts["Компоненты"], y=curr_parts["cycle_time"], name="Cycle time — текущая",
        marker_color="#6244BB",
        text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["cycle_time"]],
        textposition="outside", cliponaxis=False, visible=False
    ))
    fig.add_trace(go.Bar(
        x=prev_parts["Компоненты"], y=prev_parts["cycle_time"], name="Cycle time — предыдущая",
        marker_color="#D6CCFF",
        text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["cycle_time"]],
        textposition="outside", cliponaxis=False, visible=False
    ))
    fig.add_trace(go.Bar(
        x=curr_parts["Компоненты"], y=curr_parts["wait_time_days"], name="Ожидание — текущая",
        marker_color="#A485E0",
        text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["wait_time_days"]],
        textposition="outside", cliponaxis=False, visible=False
    ))
    fig.add_trace(go.Bar(
        x=prev_parts["Компоненты"], y=prev_parts["wait_time_days"], name="Ожидание — предыдущая",
        marker_color="#EEE8FF",
        text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["wait_time_days"]],
        textposition="outside", cliponaxis=False, visible=False
    ))

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
                    dict(label="TTM", method="update", args=[{"visible": [True, True, False, False, False, False]}, {"barmode": "group", "yaxis": {"title": "TTM, дней"}}]),
                    dict(label="Cycle time", method="update", args=[{"visible": [False, False, True, True, False, False]}, {"barmode": "group", "yaxis": {"title": "Cycle time, дней"}}]),
                    dict(label="Ожидание", method="update", args=[{"visible": [False, False, False, False, True, True]}, {"barmode": "group", "yaxis": {"title": "Ожидание, дней"}}]),
                ],
            )
        ],
    )
    return fig


def build_weekly_metric_compare_fig(curr_parts, prev_parts, metric_col, curr_name, prev_name, curr_color, prev_color, y_title):
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=curr_parts["Компоненты"], y=curr_parts[metric_col], name=curr_name,
        marker_color=curr_color,
        text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts[metric_col]],
        textposition="outside", cliponaxis=False
    ))
    fig.add_trace(go.Bar(
        x=prev_parts["Компоненты"], y=prev_parts[metric_col], name=prev_name,
        marker_color=prev_color,
        text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts[metric_col]],
        textposition="outside", cliponaxis=False
    ))

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

    weekday_map = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
    x_labels = [weekday_map[d.weekday()] for d in current_dates]

    curr_daily = (
        current_week_df.assign(Дата=current_week_df["Дата создания"].dt.normalize())
        .groupby("Дата").size()
        .reindex(current_dates, fill_value=0)
        .reset_index(name="Задач")
    )
    curr_daily.columns = ["Дата", "Задач"]
    curr_daily["X"] = x_labels
    curr_daily["Период"] = "Текущая неделя"

    prev_daily = (
        previous_week_df.assign(Дата=previous_week_df["Дата создания"].dt.normalize())
        .groupby("Дата").size()
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
        color_discrete_map={"Текущая неделя": "#6244BB", "Предыдущая неделя": "#D6CCFF"},
        template="plotly_white",
    )

    fig.update_layout(
        height=220,
        xaxis_title=None,
        yaxis_title="Кол-во задач",
        legend_title=None,
        margin=dict(l=20, r=20, t=15, b=10),
    )
    return fig


def build_weekly_contacts_compare_fig(current_week_df, previous_week_df):
    cat_order = ["1-4", "5-10", "11-100", "100+"]

    curr_contacts = current_week_df["Количество обращений"].value_counts().reindex(cat_order, fill_value=0).reset_index()
    curr_contacts.columns = ["Количество обращений", "Кол-во"]
    curr_contacts["Период"] = "Текущая неделя"

    prev_contacts = previous_week_df["Количество обращений"].value_counts().reindex(cat_order, fill_value=0).reset_index()
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
        color_discrete_map={"Текущая неделя": "#6244BB", "Предыдущая неделя": "#D6CCFF"},
        template="plotly_white",
    )

    fig.update_layout(
        height=220,
        xaxis_title=None,
        yaxis_title="Кол-во задач",
        legend_title=None,
        margin=dict(l=20, r=20, t=15, b=10),
    )
    return fig


def build_overview_export_pdf(bundle, start_date, end_date, sel_teams, sel_res, sel_types):
    f_df = bundle["f_df"]
    fig_structure_sum = bundle["fig_structure_sum"]
    fig_structure_wait = bundle["fig_structure_wait"]
    fig_load = bundle["fig_load"]
    fig_dynamics = bundle["fig_dynamics"]
    fig_dist_ttm = bundle["fig_dist_ttm"]
    fig_dist_cycle = bundle["fig_dist_cycle"]
    fig_dist_wait = bundle["fig_dist_wait"]
    fig_contacts = bundle["fig_contacts"]

    buffer = io.BytesIO()
    page_w, page_h = landscape(A3)
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    margin = 24
    gap = 12
    content_w = page_w - 2 * margin

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

    y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Общий обзор", subtitle_lines, 1, 2)
    y_cursor = draw_kpi_grid_pdf(c, page_w, y_cursor, cards, cols=4)

    col_w = (content_w - gap) / 2
    page_bottom_y = margin
    row_h = get_two_row_chart_height(page_bottom_y, y_cursor, gap, min_height=180, max_height=270)

    draw_chart_panel(c, margin, y_cursor - row_h, col_w, row_h, "Структура времени задач по командам - суммарно", fig_structure_sum)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h, col_w, row_h, "Нагрузка по командам", fig_load)

    y_cursor = y_cursor - row_h - gap
    draw_chart_panel(c, margin, y_cursor - row_h, col_w, row_h, "Структура времени задач по командам - ожидание", fig_structure_wait)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h, col_w, row_h, "Динамика поступления задач", fig_dynamics)

    c.showPage()

    y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Общий обзор (продолжение)", subtitle_lines, 2, 2)

    row_h2 = get_two_row_chart_height(margin, y_cursor, gap, min_height=190, max_height=300)
    draw_chart_panel(c, margin, y_cursor - row_h2, col_w, row_h2, "Распределение времени задач - TTM", fig_dist_ttm)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h2, col_w, row_h2, "Распределение времени задач - Cycle time", fig_dist_cycle)

    y_cursor = y_cursor - row_h2 - gap
    draw_chart_panel(c, margin, y_cursor - row_h2, col_w, row_h2, "Распределение времени задач - ожидание", fig_dist_wait)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h2, col_w, row_h2, "Структура обращений", fig_contacts)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def build_weekly_export_pdf(bundle, sel_teams, sel_res, sel_types):
    current_week_df = bundle["current_week_df"]
    previous_week_df = bundle["previous_week_df"]
    current_metrics = bundle["current_metrics"]
    previous_metrics = bundle["previous_metrics"]
    cw_start = bundle["cw_start"]
    cw_end = bundle["cw_end"]
    pw_start = bundle["pw_start"]
    pw_end = bundle["pw_end"]

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
        draw_kpi_grid_pdf(c, page_w, y_cursor, cards, cols=4)
        c.setFillColor(PDF_TEXT)
        c.setFont(PDF_FONT_BOLD, 14)
        c.drawString(margin, page_h / 2, "Недостаточно данных для сравнения текущей и предыдущей недели.")
        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    fig_cnt_compare = bundle["fig_cnt_compare"]
    fig_ttm_only = bundle["fig_ttm_only"]
    fig_cycle_only = bundle["fig_cycle_only"]
    fig_wait_only = bundle["fig_wait_only"]
    fig_flow = bundle["fig_flow"]
    fig_contacts_compare = bundle["fig_contacts_compare"]

    y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Сравнение недель", subtitle_lines, 1, 2)
    y_cursor = draw_kpi_grid_pdf(c, page_w, y_cursor, cards, cols=4)

    col_w = (content_w - gap) / 2
    page_bottom_y = margin
    row_h = get_two_row_chart_height(page_bottom_y, y_cursor, gap, min_height=180, max_height=270)

    draw_chart_panel(c, margin, y_cursor - row_h, col_w, row_h, "Количество задач", fig_cnt_compare)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h, col_w, row_h, "TTM по командам", fig_ttm_only)

    y_cursor = y_cursor - row_h - gap
    draw_chart_panel(c, margin, y_cursor - row_h, col_w, row_h, "Cycle time по командам", fig_cycle_only)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h, col_w, row_h, "Ожидание по командам", fig_wait_only)

    c.showPage()

    y_cursor = draw_page_header(c, page_w, page_h, "Аналитика дежурств - Сравнение недель (продолжение)", subtitle_lines, 2, 2)
    row_h2 = max(220, min(320, y_cursor - margin))

    draw_chart_panel(c, margin, y_cursor - row_h2, col_w, row_h2, "Поступление задач", fig_flow)
    draw_chart_panel(c, margin + col_w + gap, y_cursor - row_h2, col_w, row_h2, "Количество обращений", fig_contacts_compare)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
