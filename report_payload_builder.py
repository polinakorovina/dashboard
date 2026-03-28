import os
import pandas as pd

from data_pipeline import read_dashboard_from_postgres
from dashboard_utils import (
    calc_metrics,
    get_week_bounds,
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


def _get_postgres_url(postgres_url=None):
    if postgres_url:
        return postgres_url

    env_url = os.getenv("POSTGRES_URL", "")
    if env_url:
        return env_url

    raise RuntimeError(
        "Не найден POSTGRES_URL. Передай postgres_url аргументом "
        "или задай переменную окружения POSTGRES_URL."
    )


def _read_dashboard_df(postgres_url=None):
    postgres_url = _get_postgres_url(postgres_url)

    df = read_dashboard_from_postgres(postgres_url)
    if df.empty:
        raise RuntimeError("Данные дашборда пустые.")

    if "Дата создания" not in df.columns:
        raise RuntimeError("В данных нет колонки 'Дата создания'.")

    return df, postgres_url


def build_report_payloads_for_period(
    start_date,
    end_date,
    postgres_url=None,
    sel_teams=None,
    sel_res=None,
    sel_types=None,
):
    df, postgres_url = _read_dashboard_df(postgres_url)

    db_min = df["Дата создания"].min().date()
    db_max = df["Дата создания"].max().date()

    start_date = max(pd.to_datetime(start_date).date(), db_min)
    end_date = min(pd.to_datetime(end_date).date(), db_max)

    if start_date > end_date:
        raise RuntimeError("Некорректный период: start_date > end_date.")

    period_days = get_period_days(start_date, end_date)
    default_granularity = get_default_granularity(period_days)

    start_d = pd.to_datetime(start_date)
    end_d = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    df_in_range = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d)].copy()
    if df_in_range.empty:
        raise RuntimeError("За выбранный период данных нет.")

    teams_in_range = sorted(df_in_range["Компоненты"].dropna().unique().tolist())
    res_in_range = sorted(df_in_range["Резолюция"].dropna().unique().tolist())
    types_in_range = sorted(df_in_range["Тип"].dropna().unique().tolist())

    if sel_teams is None:
        sel_teams = teams_in_range
    if sel_res is None:
        sel_res = res_in_range
    if sel_types is None:
        sel_types = types_in_range

    f_df = df_in_range[
        (df_in_range["Компоненты"].isin(sel_teams)) &
        (df_in_range["Резолюция"].isin(sel_res)) &
        (df_in_range["Тип"].isin(sel_types))
    ].copy()

    if f_df.empty:
        raise RuntimeError("По выбранным фильтрам данных нет.")

    base_week_df = df[
        (df["Компоненты"].isin(sel_teams)) &
        (df["Резолюция"].isin(sel_res)) &
        (df["Тип"].isin(sel_types))
    ].copy()

    if base_week_df.empty:
        raise RuntimeError("Нет данных для недельного сравнения.")

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

    time_order_df = (
        f_df.groupby("Компоненты")["ttm_days"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    t_order = time_order_df["Компоненты"].tolist()

    overview_bundle = {
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

    weekly_bundle = {
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

    return {
        "overview_bundle": overview_bundle,
        "weekly_bundle": weekly_bundle,
        "sel_teams": list(sel_teams),
        "sel_res": list(sel_res),
        "sel_types": list(sel_types),
        "start_date": start_date,
        "end_date": end_date,
        "db_min": db_min,
        "db_max": db_max,
        "postgres_url": postgres_url,
    }


def build_last_week_report_payloads(postgres_url=None, sel_teams=None, sel_res=None, sel_types=None):
    df, postgres_url = _read_dashboard_df(postgres_url)

    db_max = df["Дата создания"].max().date()
    start_date = db_max - pd.Timedelta(days=6)
    start_date = start_date.date() if hasattr(start_date, "date") else start_date
    end_date = db_max

    return build_report_payloads_for_period(
        start_date=start_date,
        end_date=end_date,
        postgres_url=postgres_url,
        sel_teams=sel_teams,
        sel_res=sel_res,
        sel_types=sel_types,
    )
