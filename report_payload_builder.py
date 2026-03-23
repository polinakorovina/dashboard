import os
from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data_pipeline import read_dashboard_from_postgres


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


def get_week_bounds(anchor_date):
    anchor_date = pd.Timestamp(anchor_date).normalize()
    current_week_start = anchor_date - pd.Timedelta(days=6)
    current_week_end = anchor_date + pd.Timedelta(hours=23, minutes=59, seconds=59)
    prev_week_start = current_week_start - pd.Timedelta(days=7)
    prev_week_end = current_week_start - pd.Timedelta(seconds=1)
    return current_week_start, current_week_end, prev_week_start, prev_week_end


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

    fig.add_trace(go.Histogram(
        x=dist_df["ttm_days"],
        name="TTM",
        marker_color="#6244BB",
        opacity=0.85,
        nbinsx=20,
        visible=True,
    ))

    fig.add_trace(go.Histogram(
        x=dist_df["cycle_time"],
        name="Cycle time",
        marker_color="#6244BB",
        opacity=0.85,
        nbinsx=20,
        visible=False,
    ))

    fig.add_trace(go.Histogram(
        x=dist_df["wait_time_days"],
        name="Ожидание",
        marker_color="#A485E0",
        opacity=0.85,
        nbinsx=20,
        visible=False,
    ))

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
                        args=[{"visible": [True, False, False]}, {"xaxis": {"title": "TTM, дни"}, "yaxis": {"title": "Количество задач"}}],
                    ),
                    dict(
                        label="Cycle time",
                        method="update",
                        args=[{"visible": [False, True, False]}, {"xaxis": {"title": "Cycle time, дни"}, "yaxis": {"title": "Количество задач"}}],
                    ),
                    dict(
                        label="Ожидание",
                        method="update",
                        args=[{"visible": [False, False, True]}, {"xaxis": {"title": "Ожидание, дни"}, "yaxis": {"title": "Количество задач"}}],
                    ),
                ],
            )
        ],
    )
    return fig


def build_distribution_single_fig(f_df, metric_col, title_label, color):
    dist_df = f_df[[metric_col]].dropna().copy()

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=dist_df[metric_col],
        name=title_label,
        marker_color=color,
        opacity=0.85,
        nbinsx=20,
    ))

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
        ordered=True,
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
            "100+": "#E1D8FF",
        },
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
        x=curr_parts["Компоненты"],
        y=curr_parts["ttm_days"],
        name="TTM — текущая",
        marker_color="#6244BB",
        text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["ttm_days"]],
        textposition="outside",
        cliponaxis=False,
        visible=True,
    ))

    fig.add_trace(go.Bar(
        x=prev_parts["Компоненты"],
        y=prev_parts["ttm_days"],
        name="TTM — предыдущая",
        marker_color="#D6CCFF",
        text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["ttm_days"]],
        textposition="outside",
        cliponaxis=False,
        visible=True,
    ))

    fig.add_trace(go.Bar(
        x=curr_parts["Компоненты"],
        y=curr_parts["cycle_time"],
        name="Cycle time — текущая",
        marker_color="#6244BB",
        text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["cycle_time"]],
        textposition="outside",
        cliponaxis=False,
        visible=False,
    ))

    fig.add_trace(go.Bar(
        x=prev_parts["Компоненты"],
        y=prev_parts["cycle_time"],
        name="Cycle time — предыдущая",
        marker_color="#D6CCFF",
        text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["cycle_time"]],
        textposition="outside",
        cliponaxis=False,
        visible=False,
    ))

    fig.add_trace(go.Bar(
        x=curr_parts["Компоненты"],
        y=curr_parts["wait_time_days"],
        name="Ожидание — текущая",
        marker_color="#A485E0",
        text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts["wait_time_days"]],
        textposition="outside",
        cliponaxis=False,
        visible=False,
    ))

    fig.add_trace(go.Bar(
        x=prev_parts["Компоненты"],
        y=prev_parts["wait_time_days"],
        name="Ожидание — предыдущая",
        marker_color="#EEE8FF",
        text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts["wait_time_days"]],
        textposition="outside",
        cliponaxis=False,
        visible=False,
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
        x=curr_parts["Компоненты"],
        y=curr_parts[metric_col],
        name=curr_name,
        marker_color=curr_color,
        text=[f"{v:.2f}" if v > 0 else "" for v in curr_parts[metric_col]],
        textposition="outside",
        cliponaxis=False,
    ))

    fig.add_trace(go.Bar(
        x=prev_parts["Компоненты"],
        y=prev_parts[metric_col],
        name=prev_name,
        marker_color=prev_color,
        text=[f"{v:.2f}" if v > 0 else "" for v in prev_parts[metric_col]],
        textposition="outside",
        cliponaxis=False,
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


def _get_postgres_url(postgres_url=None):
    if postgres_url:
        return postgres_url

    env_url = os.getenv("POSTGRES_URL", "")
    if env_url:
        return env_url

    raise RuntimeError("Не найден POSTGRES_URL. Передай postgres_url аргументом или задай переменную окружения POSTGRES_URL.")


def build_report_payloads_for_period(start_date, end_date, postgres_url=None, sel_teams=None, sel_res=None, sel_types=None):
    postgres_url = _get_postgres_url(postgres_url)

    df = read_dashboard_from_postgres(postgres_url)
    if df.empty:
        raise RuntimeError("Данные дашборда пустые.")

    db_min = df["Дата создания"].min().date()
    db_max = df["Дата создания"].max().date()

    # страховка, если кто-то передал период вне диапазона
    start_date = max(pd.to_datetime(start_date).date(), db_min)
    end_date = min(pd.to_datetime(end_date).date(), db_max)

    if start_date > end_date:
        raise RuntimeError("Некорректный период: start_date > end_date")

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
    }
