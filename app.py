import streamlit as st
import pandas as pd
from datetime import timedelta, date

from data_pipeline import read_dashboard_from_postgres
from import_utils import process_uploaded_files
from export_utils import build_overview_export_pdf, build_weekly_export_pdf
from dashboard_utils import (
    get_week_bounds,
    calc_metrics,
    get_period_days,
    get_default_granularity,
    build_structure_interactive_fig,
    build_structure_sum_fig,
    build_structure_wait_fig,
    build_load_fig,
    build_dynamics_fig,
    build_distribution_interactive_fig,
    build_distribution_single_fig,
    build_contacts_fig,
    build_weekly_count_fig,
    build_weekly_ttm_interactive_fig,
    build_weekly_metric_compare_fig,
    build_weekly_flow_fig,
    build_weekly_contacts_compare_fig,
)

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

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] {
        background: #F7F2FA !important;
        height: 1.6rem !important;
        min-height: 1.6rem !important;
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

    [data-testid="stDateInput"] [aria-selected="true"] {
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


df = st.session_state.get("data", pd.DataFrame())
if df.empty:
    st.warning("После обработки данные пустые.")
    st.stop()

db_min = df["Дата создания"].min().date()
db_max = df["Дата создания"].max().date()

default_start = max(db_min, db_max - timedelta(days=6))
default_range = (default_start, db_max)

st.sidebar.markdown(
    "<div style='font-size:20px; font-weight:600; margin-bottom:-35px;'>Выбор даты</div>",
    unsafe_allow_html=True,
)

date_range = st.sidebar.date_input(
    "Период анализа",
    value=st.session_state.get("date_range", default_range),
    min_value=db_min,
    max_value=db_max,
    key="date_range",
    format="DD.MM.YYYY",
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

teams_in_range = sorted(df_in_range["Компоненты"].unique().tolist())
res_in_range = sorted(df_in_range["Резолюция"].unique().tolist())
types_in_range = sorted(df_in_range["Тип"].unique().tolist())

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
    key="sel_teams",
)

sel_res = st.sidebar.multiselect(
    "Резолюции",
    res_in_range,
    default=st.session_state.get("sel_res", res_in_range),
    key="sel_res",
)

sel_types = st.sidebar.multiselect(
    "Тип",
    types_in_range,
    default=st.session_state.get("sel_types", types_in_range),
    key="sel_types",
)

f_df = df_in_range[
    (df_in_range["Компоненты"].isin(sel_teams)) &
    (df_in_range["Резолюция"].isin(sel_res)) &
    (df_in_range["Тип"].isin(sel_types))
].copy()

if f_df.empty:
    st.warning("По выбранным фильтрам данных нет.")
    st.stop()

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


def get_overview_sig():
    return (
        st.session_state.get("data_version", 0),
        str(start_date),
        str(end_date),
        tuple(sel_teams),
        tuple(sel_res),
        tuple(sel_types),
        default_granularity,
        len(f_df),
    )


def get_weekly_sig():
    return (
        st.session_state.get("data_version", 0),
        str(cw_start),
        str(cw_end),
        str(pw_start),
        str(pw_end),
        tuple(sel_teams),
        tuple(sel_res),
        tuple(sel_types),
        len(current_week_df),
        len(previous_week_df),
    )


def get_overview_bundle():
    sig = get_overview_sig()
    cache = st.session_state.get("overview_bundle_cache", {})

    if cache.get("sig") == sig:
        return cache["bundle"]

    time_order_df = (
        f_df.groupby("Компоненты")["ttm_days"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    t_order = time_order_df["Компоненты"].tolist()

    bundle = {
        "f_df": f_df.copy(),
        "t_order": t_order,
        "fig_structure_interactive": build_structure_interactive_fig(f_df, t_order),
        "fig_structure_sum": build_structure_sum_fig(f_df, t_order),
        "fig_structure_wait": build_structure_wait_fig(f_df, t_order),
        "fig_load": build_load_fig(f_df, t_order),
        "fig_dynamics": build_dynamics_fig(f_df, default_granularity=default_granularity),
        "fig_dist_interactive": build_distribution_interactive_fig(f_df),
        "fig_dist_ttm": build_distribution_single_fig(f_df, "ttm_days", "TTM", "#6244BB"),
        "fig_dist_cycle": build_distribution_single_fig(f_df, "cycle_time", "Cycle time", "#6244BB"),
        "fig_dist_wait": build_distribution_single_fig(f_df, "wait_time_days", "Ожидание", "#A485E0"),
        "fig_contacts": build_contacts_fig(f_df),
    }

    st.session_state["overview_bundle_cache"] = {"sig": sig, "bundle": bundle}
    return bundle


def get_weekly_bundle():
    sig = get_weekly_sig()
    cache = st.session_state.get("weekly_bundle_cache", {})

    if cache.get("sig") == sig:
        return cache["bundle"]

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

    bundle = {
        "current_week_df": current_week_df.copy(),
        "previous_week_df": previous_week_df.copy(),
        "current_metrics": current_metrics,
        "previous_metrics": previous_metrics,
        "cw_start": cw_start,
        "cw_end": cw_end,
        "pw_start": pw_start,
        "pw_end": pw_end,
        "fig_cnt_compare": build_weekly_count_fig(current_week_df, previous_week_df, team_order_week),
        "fig_ttm_interactive": build_weekly_ttm_interactive_fig(curr_parts, prev_parts),
        "fig_ttm_only": build_weekly_metric_compare_fig(
            curr_parts, prev_parts, "ttm_days",
            "TTM — текущая", "TTM — предыдущая",
            "#6244BB", "#D6CCFF", "TTM, дней",
        ),
        "fig_cycle_only": build_weekly_metric_compare_fig(
            curr_parts, prev_parts, "cycle_time",
            "Cycle time — текущая", "Cycle time — предыдущая",
            "#6244BB", "#D6CCFF", "Cycle time, дней",
        ),
        "fig_wait_only": build_weekly_metric_compare_fig(
            curr_parts, prev_parts, "wait_time_days",
            "Ожидание — текущая", "Ожидание — предыдущая",
            "#A485E0", "#EEE8FF", "Ожидание, дней",
        ),
        "fig_flow": build_weekly_flow_fig(current_week_df, previous_week_df, cw_start, cw_end, pw_start, pw_end),
        "fig_contacts_compare": build_weekly_contacts_compare_fig(current_week_df, previous_week_df),
    }

    st.session_state["weekly_bundle_cache"] = {"sig": sig, "bundle": bundle}
    return bundle


st.radio(
    "Раздел",
    ["Общий обзор", "Сравнение недель"],
    horizontal=True,
    key="active_view",
    label_visibility="collapsed",
)

current_active_view = st.session_state.get("active_view", "Общий обзор")


def top_bar_fragment(current_active_view, export_filename="dashboard_export.pdf"):
    title_col, import_col, export_col = st.columns([8, 1, 1])

    with title_col:
        st.markdown('<div class="main-header">Аналитика дежурств</div>', unsafe_allow_html=True)

    with import_col:
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        if st.button("Импорт", key="toggle_upload_btn"):
            st.session_state["show_upload_block"] = not st.session_state["show_upload_block"]

    with export_col:
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

        def _build_pdf_on_click():
            if current_active_view == "Общий обзор":
                bundle = get_overview_bundle()
                return build_overview_export_pdf(
                    bundle=bundle,
                    start_date=start_date,
                    end_date=end_date,
                    sel_teams=sel_teams,
                    sel_res=sel_res,
                    sel_types=sel_types,
                )

            bundle = get_weekly_bundle()
            return build_weekly_export_pdf(
                bundle=bundle,
                sel_teams=sel_teams,
                sel_res=sel_res,
                sel_types=sel_types,
            )

        st.download_button(
            "Скачать PDF",
            data=_build_pdf_on_click,
            file_name=export_filename,
            mime="application/pdf",
            key="download_export_pdf_btn",
            on_click="ignore",
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
            key="uploaded_files_main",
        )

        if uploaded_files and len(uploaded_files) != 2:
            st.warning("Пожалуйста, загрузите ровно 2 файла.")

        if st.button("Обработать файлы", key="process_files_btn"):
            try:
                final_df, inserted_rows = process_uploaded_files(uploaded_files, POSTGRES_URL)

                read_dashboard_cached.clear()

                st.session_state["data"] = final_df
                st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
                st.session_state["overview_bundle_cache"] = {}
                st.session_state["weekly_bundle_cache"] = {}

                st.success(f"Файлы успешно загружены. В базу добавлено новых строк: {inserted_rows}")
                st.rerun()
            except Exception as e:
                st.error(str(e))


if not weekly_ready and current_active_view == "Сравнение недель":
    export_filename = f"dashboard_weekly_{pd.to_datetime(start_date).strftime('%Y%m%d')}_{pd.to_datetime(end_date).strftime('%Y%m%d')}.pdf"
else:
    export_filename = f"dashboard_{pd.to_datetime(start_date).strftime('%Y%m%d')}_{pd.to_datetime(end_date).strftime('%Y%m%d')}.pdf"

top_bar_fragment(current_active_view=current_active_view, export_filename=export_filename)


def render_overview(bundle):
    f_df_local = bundle["f_df"]

    k1, k2, k3, k4, k5, k6, k7 = st.columns(7, gap="small")

    with k1:
        kpi_card("Всего задач", f"{len(f_df_local)}", "Общее число задач за выбранный период, которые поступили в работу")

    with k2:
        med = f_df_local["ttm_days"].median() if len(f_df_local) else 0.0
        avg = f_df_local["ttm_days"].mean() if len(f_df_local) else 0.0
        kpi_card(
            "TTM (дн)",
            f"{avg:.2f}",
            "Сколько в среднем времени занимал путь задач по процессу целиком",
            subvalue=f"медиана: {med:.2f}",
        )

    with k3:
        med = f_df_local["cycle_time"].median() if len(f_df_local) else 0.0
        avg = f_df_local["cycle_time"].mean() if len(f_df_local) else 0.0
        kpi_card(
            "Cycle time (дн)",
            f"{avg:.2f}",
            "Среднее время активной работы над задачами",
            subvalue=f"медиана: {med:.2f}",
        )

    with k4:
        avg = f_df_local["wait_time_days"].mean() if len(f_df_local) else 0.0
        med = f_df_local["wait_time_days"].median() if len(f_df_local) else 0.0
        kpi_card(
            "Ожидание (дн)",
            f"{avg:.2f}",
            "Среднее время вне активной работы",
            subvalue=f"медиана: {med:.2f}",
        )

    with k5:
        late = ((f_df_local["Резолюция"] == "Позже").mean() * 100) if len(f_df_local) else 0
        kpi_card("Позже", f"{late:.1f}%", "Доля задач, которые решены позже", color="#E45757" if late > 50 else "#4CAF7D")

    with k6:
        active = (f_df_local["cycle_time"].sum() / f_df_local["ttm_days"].sum()) * 100 if f_df_local["ttm_days"].sum() > 0 else 0
        kpi_card("Flow Efficiency", f"{active:.0f}%", "Cycle time / TTM", color="#E45757" if active < 50 else "#4CAF7D")

    with k7:
        pingpong_share = ((f_df_local["Пинг-понг обращения"] > 1).mean() * 100) if len(f_df_local) else 0.0
        tasks_with_pingpong = (f_df_local["Пинг-понг обращения"] > 1).sum() if len(f_df_local) else 0
        kpi_card(
            "Пинг-понг > 1",
            f"{pingpong_share:.1f}%",
            "Доля задач, которые передавались между командами более одного раза",
            subvalue=f"задач: {tasks_with_pingpong}",
            color="#E45757" if pingpong_share > 20 else "#4CAF7D",
            hint_side="left",
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="small")

    with c1:
        st.markdown(
            '<div class="card-header">Структура времени задач по командам</div>'
            '<span class="hint-icon" data-hint="Можно посмотреть суммарно Cycle time + ожидание или только этапы ожидания">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_structure_interactive"], use_container_width=True, config={"displayModeBar": False})

    with c2:
        st.markdown(
            '<div class="card-header">Нагрузка по командам</div>'
            '<span class="hint-icon" data-hint="Количество задач, которые были взяты в работу по командам">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_load"], use_container_width=True, config={"displayModeBar": False})

    b1, b2, b3 = st.columns(3, gap="small")

    with b1:
        st.markdown(
            '<div class="card-header">Динамика поступления задач</div>'
            '<span class="hint-icon" data-hint="Количество новых задач по дням, неделям или месяцам">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_dynamics"], use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    with b2:
        st.markdown(
            '<div class="card-header">Распределение времени задач</div>'
            '<span class="hint-icon" data-hint="Можно посмотреть распределение TTM, Cycle time или ожидания по задачам">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_dist_interactive"], use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

    with b3:
        st.markdown(
            '<div class="card-header">Структура обращений</div>'
            '<span class="hint-icon" data-hint="Распределение задач по категориям количества обращений">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_contacts"], use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})


def render_weekly(bundle):
    st.markdown(
        f"""
        <div style="font-size:16px; font-weight:600; margin-bottom:8px;">
            Текущая неделя: {bundle['cw_start'].strftime('%d.%m.%Y')} — {bundle['cw_end'].strftime('%d.%m.%Y')}
            <span style="color:#7E8694; font-weight:400;">&nbsp;&nbsp;vs&nbsp;&nbsp;</span>
            Предыдущая неделя: {bundle['pw_start'].strftime('%d.%m.%Y')} — {bundle['pw_end'].strftime('%d.%m.%Y')}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not weekly_ready:
        st.warning("Недостаточно данных для сравнения текущей и предыдущей недели.")
        return

    current_metrics_local = bundle["current_metrics"]
    previous_metrics_local = bundle["previous_metrics"]

    w1, w2, w3, w4, w5, w6, w7 = st.columns(7, gap="small")

    with w1:
        kpi_compare_card("Всего задач", current_metrics_local["tasks_total"], previous_metrics_local["tasks_total"], hint="Количество задач за текущую неделю", as_int=True)
    with w2:
        kpi_compare_card("TTM (дн)", current_metrics_local["ttm"], previous_metrics_local["ttm"], hint="Среднее время от открытия задачи до её закрытия")
    with w3:
        kpi_compare_card("Cycle time (дн)", current_metrics_local["cycle"], previous_metrics_local["cycle"], hint="Среднее время активной работы")
    with w4:
        kpi_compare_card("Ожидание (дн)", current_metrics_local["wait"], previous_metrics_local["wait"], hint="Среднее время ожидания")
    with w5:
        kpi_compare_card("Позже", current_metrics_local["later_pct"], previous_metrics_local["later_pct"], hint="Доля задач с резолюцией 'Позже'", is_percent=True)
    with w6:
        kpi_compare_card("Flow Efficiency", current_metrics_local["active_pct"], previous_metrics_local["active_pct"], hint="Доля активной работы в общем времени", is_percent=True)
    with w7:
        kpi_compare_card("Пинг-понг > 1", current_metrics_local["pingpong_share"], previous_metrics_local["pingpong_share"], hint="Доля задач, которые передавались между командами более одного раза", is_percent=True)

    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

    g1, g2 = st.columns(2, gap="small")

    with g1:
        st.markdown(
            '<div class="card-header">Количество задач</div>'
            '<span class="hint-icon" data-hint="Сравнение объёма задач по командам за две недели">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_cnt_compare"], use_container_width=True, config={"displayModeBar": False})

    with g2:
        st.markdown(
            '<div class="card-header">TTM по командам</div>'
            '<span class="hint-icon" data-hint="Можно посмотреть TTM, Cycle time или ожидание по командам за две недели">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_ttm_interactive"], use_container_width=True, config={"displayModeBar": False})

    g3, g4 = st.columns(2, gap="small")

    with g3:
        st.markdown(
            '<div class="card-header">Поступление задач</div>'
            '<span class="hint-icon" data-hint="Сравнение количества новых задач по дням для текущей недели и предыдущей">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_flow"], use_container_width=True, config={"displayModeBar": False})

    with g4:
        st.markdown(
            '<div class="card-header">Количество обращений</div>'
            '<span class="hint-icon" data-hint="Сравнение категорий количества обращений за две недели">?</span>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(bundle["fig_contacts_compare"], use_container_width=True, config={"displayModeBar": False})


if current_active_view == "Общий обзор":
    overview_bundle = get_overview_bundle()
    render_overview(overview_bundle)
else:
    weekly_bundle = get_weekly_bundle()
    render_weekly(weekly_bundle)
