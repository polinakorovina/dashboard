import os
import time
import json
import statistics
from datetime import timedelta

import pandas as pd

from data_pipeline import read_dashboard_from_postgres, prepare_dashboard_data
from export_utils import build_overview_export_pdf, build_weekly_export_pdf
from dashboard_utils import (
    get_week_bounds,
    calc_metrics,
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

POSTGRES_URL = os.getenv("POSTGRES_URL")

if not POSTGRES_URL:
    raise ValueError("Не задана переменная окружения POSTGRES_URL")


def measure_once(fn):
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    return elapsed, result


def measure_many(name, fn, runs=5):
    times = []
    result = None
    for _ in range(runs):
        elapsed, result = measure_once(fn)
        times.append(elapsed)

    return {
        "operation": name,
        "runs": runs,
        "min_sec": round(min(times), 4),
        "max_sec": round(max(times), 4),
        "avg_sec": round(statistics.mean(times), 4),
        "median_sec": round(statistics.median(times), 4),
    }, result


def build_overview_bundle_local(df: pd.DataFrame):
    db_min = df["Дата создания"].min().date()
    db_max = df["Дата создания"].max().date()

    start_date = max(db_min, db_max - timedelta(days=6))
    end_date = db_max

    start_d = pd.to_datetime(start_date)
    end_d = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    f_df = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d)].copy()
    if f_df.empty:
        raise ValueError("Для overview bundle после фильтрации нет данных.")

    period_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
    default_granularity = get_default_granularity(period_days)

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
        "start_date": start_date,
        "end_date": end_date,
        "sel_teams": sorted(f_df["Компоненты"].dropna().unique().tolist()),
        "sel_res": sorted(f_df["Резолюция"].dropna().unique().tolist()),
        "sel_types": sorted(f_df["Тип"].dropna().unique().tolist()),
    }
    return bundle


def build_weekly_bundle_local(df: pd.DataFrame):
    anchor_date = df["Дата создания"].max()
    cw_start, cw_end, pw_start, pw_end = get_week_bounds(anchor_date)

    current_week_df = df[
        (df["Дата создания"] >= cw_start) &
        (df["Дата создания"] <= cw_end)
    ].copy()

    previous_week_df = df[
        (df["Дата создания"] >= pw_start) &
        (df["Дата создания"] <= pw_end)
    ].copy()

    if current_week_df.empty or previous_week_df.empty:
        raise ValueError("Недостаточно данных для weekly bundle.")

    current_metrics = calc_metrics(current_week_df)
    previous_metrics = calc_metrics(previous_week_df)

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
        "sel_teams": sorted(df["Компоненты"].dropna().unique().tolist()),
        "sel_res": sorted(df["Резолюция"].dropna().unique().tolist()),
        "sel_types": sorted(df["Тип"].dropna().unique().tolist()),
    }
    return bundle


def main():
    results = []

    read_result, raw_df = measure_many(
        "read_dashboard_from_postgres",
        lambda: read_dashboard_from_postgres(POSTGRES_URL),
        runs=5,
    )
    results.append(read_result)

    if raw_df.empty:
        raise ValueError("В PostgreSQL нет данных.")

    prep_result, prepared_df = measure_many(
        "prepare_dashboard_data",
        lambda: prepare_dashboard_data(raw_df),
        runs=5,
    )
    results.append(prep_result)

    overview_result, overview_bundle = measure_many(
        "build_overview_bundle",
        lambda: build_overview_bundle_local(prepared_df),
        runs=3,
    )
    results.append(overview_result)

    weekly_result, weekly_bundle = measure_many(
        "build_weekly_bundle",
        lambda: build_weekly_bundle_local(prepared_df),
        runs=3,
    )
    results.append(weekly_result)

    overview_pdf_result, _ = measure_many(
        "build_overview_export_pdf",
        lambda: build_overview_export_pdf(
            bundle=overview_bundle,
            start_date=overview_bundle["start_date"],
            end_date=overview_bundle["end_date"],
            sel_teams=overview_bundle["sel_teams"],
            sel_res=overview_bundle["sel_res"],
            sel_types=overview_bundle["sel_types"],
        ),
        runs=3,
    )
    results.append(overview_pdf_result)

    weekly_pdf_result, _ = measure_many(
        "build_weekly_export_pdf",
        lambda: build_weekly_export_pdf(
            bundle=weekly_bundle,
            sel_teams=weekly_bundle["sel_teams"],
            sel_res=weekly_bundle["sel_res"],
            sel_types=weekly_bundle["sel_types"],
        ),
        runs=3,
    )
    results.append(weekly_pdf_result)

    first_overview_time, _ = measure_once(lambda: build_overview_bundle_local(prepared_df))
    second_overview_time, _ = measure_once(lambda: build_overview_bundle_local(prepared_df))

    results.append({
        "operation": "overview_first_vs_second_run",
        "first_run_sec": round(first_overview_time, 4),
        "second_run_sec": round(second_overview_time, 4),
    })

    first_weekly_time, _ = measure_once(lambda: build_weekly_bundle_local(prepared_df))
    second_weekly_time, _ = measure_once(lambda: build_weekly_bundle_local(prepared_df))

    results.append({
        "operation": "weekly_first_vs_second_run",
        "first_run_sec": round(first_weekly_time, 4),
        "second_run_sec": round(second_weekly_time, 4),
    })

    print(json.dumps(results, ensure_ascii=False, indent=2))

    with open("perf_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
