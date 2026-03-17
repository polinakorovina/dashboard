import io
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import yadisk
from PIL import Image, ImageDraw, ImageFont


TTM_STAGES = ["Сбор данных", "Открыт", "Заблокирован", "На стороне менеджера", "Бэклог разработки", "В работе"]
CYCLE_STAGES = ["Бэклог разработки", "В работе"]
WAIT_STAGES = [stage for stage in TTM_STAGES if stage not in CYCLE_STAGES]

TOKEN = os.getenv("YANDEX_TOKEN", "")
REMOTE_DB_PATH = os.getenv("YANDEX_DB_PATH", "/Data/my_database.db")
REMOTE_REPORTS_FOLDER = os.getenv("YANDEX_REPORTS_FOLDER", "/dashboard_reports")
LOCAL_DB_PATH = "local_view.db"

y = yadisk.YaDisk(token=TOKEN)


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return None


def _fig_to_pil(fig, width=1200, height=520, scale=2):
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=scale)
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def _save_bytesio_image(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_round_rect(draw, box, fill, outline=None, radius=18, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _draw_text(draw, xy, text, font, fill="black"):
    draw.text(xy, str(text), font=font, fill=fill)


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


def load_data():
    if not TOKEN:
        raise RuntimeError("Не задан YANDEX_TOKEN")

    if not y.check_token():
        raise RuntimeError("YANDEX_TOKEN невалидный")

    if not y.exists(REMOTE_DB_PATH):
        raise FileNotFoundError(f"База не найдена на Яндекс Диске: {REMOTE_DB_PATH}")

    if Path(LOCAL_DB_PATH).exists():
        Path(LOCAL_DB_PATH).unlink()

    y.download(REMOTE_DB_PATH, LOCAL_DB_PATH)

    conn = sqlite3.connect(LOCAL_DB_PATH)
    try:
        df_ = pd.read_sql("SELECT * FROM tasks", conn)
    finally:
        conn.close()

    if "Дата создания" not in df_.columns:
        raise ValueError("В таблице нет колонки 'Дата создания'")

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


def build_general_overview_png(
    period_label,
    total_tasks,
    ttm_avg,
    ttm_med,
    cycle_avg,
    cycle_med,
    wait_avg,
    wait_med,
    later_pct,
    active_pct,
    pingpong_avg,
    pingpong_med,
    fig_a,
    fig_l,
    fig_d,
    fig_dist,
    fig_contacts
):
    W = 2000
    PAD = 28
    kpi_gap = 16
    two_col_gap = 22
    three_col_gap = 18

    title_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    subtitle_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    card_title_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 21)
    card_value_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    card_sub_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    section_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)

    img_a = _fig_to_pil(fig_a, width=1200, height=520, scale=2)
    img_l = _fig_to_pil(fig_l, width=1200, height=520, scale=2)
    img_d = _fig_to_pil(fig_d, width=1000, height=500, scale=2)
    img_dist = _fig_to_pil(fig_dist, width=1000, height=500, scale=2)
    img_contacts = _fig_to_pil(fig_contacts, width=1000, height=500, scale=2)

    kpi_cols = 7
    kpi_w = int((W - PAD * 2 - kpi_gap * (kpi_cols - 1)) / kpi_cols)
    kpi_h = 125
    two_col_w = int((W - PAD * 2 - two_col_gap) / 2)
    three_col_w = int((W - PAD * 2 - three_col_gap * 2) / 3)

    H = 150 + kpi_h + 24 + 560 + 28 + 540 + 30

    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)

    _draw_text(draw, (PAD, 22), "Аналитика дежурств — Общий обзор", title_font, "black")
    _draw_text(draw, (PAD, 68), f"Период анализа: {period_label}", subtitle_font, "#444444")
    _draw_text(draw, (PAD, 98), f"Сформировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}", subtitle_font, "#666666")

    kpi_data = [
        ("Всего задач", f"{total_tasks}", None, "#6244BB"),
        ("TTM в днях", f"{ttm_avg:.2f}", f"медиана: {ttm_med:.2f}", "#6244BB"),
        ("Cycle time (дн)", f"{cycle_avg:.2f}", f"медиана: {cycle_med:.2f}", "#6244BB"),
        ("Ожидание (дн)", f"{wait_avg:.2f}", f"медиана: {wait_med:.2f}", "#6244BB"),
        ("Позже %", f"{later_pct:.1f}%", None, "#E45757" if later_pct > 50 else "#4CAF7D"),
        ("Flow Efficiency %", f"{active_pct:.0f}%", None, "#E45757" if active_pct < 50 else "#4CAF7D"),
        ("Передачи между командами", f"{pingpong_avg:.2f}", f"медиана: {pingpong_med:.2f}", "#6244BB"),
    ]

    y0 = 135
    for i, (title, value, sub, color) in enumerate(kpi_data):
        x = PAD + i * (kpi_w + kpi_gap)
        _draw_round_rect(draw, (x, y0, x + kpi_w, y0 + kpi_h), fill="#ffffff", outline="#E6E9EF", radius=20)
        _draw_text(draw, (x + 16, y0 + 14), title, card_title_font, "#1A1C1E")
        _draw_text(draw, (x + 16, y0 + 52), value, card_value_font, color)
        if sub:
            _draw_text(draw, (x + 16, y0 + 95), sub, card_sub_font, "#7E8694")

    row2_y = y0 + kpi_h + 28

    _draw_text(draw, (PAD, row2_y - 24), "Структура времени задачи", section_font, "#1A1C1E")
    _draw_round_rect(draw, (PAD, row2_y, PAD + two_col_w, row2_y + 520), fill="white", outline="#ECEAF3", radius=20)
    canvas.paste(img_a.resize((two_col_w - 16, 504)), (PAD + 8, row2_y + 8))

    x2 = PAD + two_col_w + two_col_gap
    _draw_text(draw, (x2, row2_y - 24), "Нагрузка по командам", section_font, "#1A1C1E")
    _draw_round_rect(draw, (x2, row2_y, x2 + two_col_w, row2_y + 520), fill="white", outline="#ECEAF3", radius=20)
    canvas.paste(img_l.resize((two_col_w - 16, 504)), (x2 + 8, row2_y + 8))

    row3_y = row2_y + 520 + 32

    titles = [
        "Динамика поступления задач",
        "Распределение Cycle Time и ожидания",
        "Структура обращений",
    ]
    imgs = [img_d, img_dist, img_contacts]

    for i in range(3):
        x = PAD + i * (three_col_w + three_col_gap)
        _draw_text(draw, (x, row3_y - 24), titles[i], section_font, "#1A1C1E")
        _draw_round_rect(draw, (x, row3_y, x + three_col_w, row3_y + 500), fill="white", outline="#ECEAF3", radius=20)
        canvas.paste(imgs[i].resize((three_col_w - 16, 484)), (x + 8, row3_y + 8))

    return _save_bytesio_image(canvas)


def build_weekly_compare_png(
    current_label,
    previous_label,
    current_metrics,
    previous_metrics,
    fig_cnt_compare,
    fig_ttm_compare,
    fig_flow,
    fig_contacts_compare
):
    W = 2000
    PAD = 28
    kpi_gap = 16
    two_col_gap = 22

    title_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    subtitle_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    card_title_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 19)
    card_value_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 29)
    card_sub_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    section_font = _font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)

    img_cnt = _fig_to_pil(fig_cnt_compare, width=1200, height=500, scale=2)
    img_ttm = _fig_to_pil(fig_ttm_compare, width=1200, height=500, scale=2)
    img_flow = _fig_to_pil(fig_flow, width=1200, height=460, scale=2)
    img_contacts = _fig_to_pil(fig_contacts_compare, width=1200, height=460, scale=2)

    kpi_cols = 7
    kpi_w = int((W - PAD * 2 - kpi_gap * (kpi_cols - 1)) / kpi_cols)
    kpi_h = 150
    two_col_w = int((W - PAD * 2 - two_col_gap) / 2)

    H = 155 + kpi_h + 28 + 520 + 30 + 480 + 30

    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)

    _draw_text(draw, (PAD, 22), "Аналитика дежурств — Сравнение недель", title_font, "black")
    _draw_text(draw, (PAD, 68), f"Текущая неделя: {current_label}", subtitle_font, "#444444")
    _draw_text(draw, (PAD, 98), f"Предыдущая неделя: {previous_label}", subtitle_font, "#666666")

    def diff_text(curr, prev, is_percent=False, digits=2, as_int=False):
        if pd.isna(curr) or pd.isna(prev):
            return "н/д"
        diff = curr - prev
        sign = "+" if diff > 0 else ""
        if as_int:
            return f"{sign}{int(round(diff))}"
        if is_percent:
            return f"{sign}{diff:.1f} п.п."
        return f"{sign}{diff:.{digits}f}"

    cards = [
        ("Всего задач", current_metrics["tasks_total"], previous_metrics["tasks_total"], False, True),
        ("TTM (дн)", current_metrics["ttm"], previous_metrics["ttm"], False, False),
        ("Cycle time (дн)", current_metrics["cycle"], previous_metrics["cycle"], False, False),
        ("Ожидание (дн)", current_metrics["wait"], previous_metrics["wait"], False, False),
        ("Позже", current_metrics["later_pct"], previous_metrics["later_pct"], True, False),
        ("Flow Efficiency", current_metrics["active_pct"], previous_metrics["active_pct"], True, False),
        ("Пинг-понг", current_metrics["pingpong"], previous_metrics["pingpong"], False, False),
    ]

    y0 = 135
    for i, (title, curr, prev, is_percent, as_int) in enumerate(cards):
        x = PAD + i * (kpi_w + kpi_gap)
        _draw_round_rect(draw, (x, y0, x + kpi_w, y0 + kpi_h), fill="#ffffff", outline="#E6E9EF", radius=20)
        _draw_text(draw, (x + 12, y0 + 12), title, card_title_font, "#1A1C1E")

        if as_int:
            curr_str = f"{int(round(curr))}"
            prev_str = f"{int(round(prev))}"
        elif is_percent:
            curr_str = f"{curr:.1f}%"
            prev_str = f"{prev:.1f}%"
        else:
            curr_str = f"{curr:.2f}"
            prev_str = f"{prev:.2f}"

        _draw_text(draw, (x + 12, y0 + 45), curr_str, card_value_font, "#6244BB")
        _draw_text(draw, (x + 12, y0 + 88), f"Пред. неделя: {prev_str}", card_sub_font, "#7E8694")
        _draw_text(draw, (x + 12, y0 + 114), f"Изменение: {diff_text(curr, prev, is_percent=is_percent, as_int=as_int)}", card_sub_font, "#4F46E5")

    row2_y = y0 + kpi_h + 28

    _draw_text(draw, (PAD, row2_y - 24), "Количество задач", section_font, "#1A1C1E")
    _draw_round_rect(draw, (PAD, row2_y, PAD + two_col_w, row2_y + 500), fill="white", outline="#ECEAF3", radius=20)
    canvas.paste(img_cnt.resize((two_col_w - 16, 484)), (PAD + 8, row2_y + 8))

    x2 = PAD + two_col_w + two_col_gap
    _draw_text(draw, (x2, row2_y - 24), "TTM по командам", section_font, "#1A1C1E")
    _draw_round_rect(draw, (x2, row2_y, x2 + two_col_w, row2_y + 500), fill="white", outline="#ECEAF3", radius=20)
    canvas.paste(img_ttm.resize((two_col_w - 16, 484)), (x2 + 8, row2_y + 8))

    row3_y = row2_y + 500 + 32

    _draw_text(draw, (PAD, row3_y - 24), "Поступление задач", section_font, "#1A1C1E")
    _draw_round_rect(draw, (PAD, row3_y, PAD + two_col_w, row3_y + 460), fill="white", outline="#ECEAF3", radius=20)
    canvas.paste(img_flow.resize((two_col_w - 16, 444)), (PAD + 8, row3_y + 8))

    _draw_text(draw, (x2, row3_y - 24), "Количество обращений", section_font, "#1A1C1E")
    _draw_round_rect(draw, (x2, row3_y, x2 + two_col_w, row3_y + 460), fill="white", outline="#ECEAF3", radius=20)
    canvas.paste(img_contacts.resize((two_col_w - 16, 444)), (x2 + 8, row3_y + 8))

    return _save_bytesio_image(canvas)


def upload_bytes_to_yadisk(png_bytes, remote_path):
    tmp_name = "temp_report.png"
    with open(tmp_name, "wb") as f:
        f.write(png_bytes.getvalue())

    folder = os.path.dirname(remote_path)
    if folder and not y.exists(folder):
        y.mkdir(folder)

    if y.exists(remote_path):
        y.remove(remote_path, permanently=True)

    y.upload(tmp_name, remote_path)
    os.remove(tmp_name)


def main():
    df = load_data()

    db_min = df["Дата создания"].min().date()
    db_max = df["Дата создания"].max().date()

    start_date = max(db_min, db_max - timedelta(days=6))
    end_date = db_max

    start_d = pd.to_datetime(start_date)
    end_d = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    df_in_range = df[(df["Дата создания"] >= start_d) & (df["Дата создания"] <= end_d)].copy()
    if df_in_range.empty:
        raise RuntimeError("Нет данных за период.")

    sel_teams = sorted(df_in_range["Компоненты"].dropna().unique().tolist())
    sel_res = sorted(df_in_range["Резолюция"].dropna().unique().tolist())
    sel_types = sorted(df_in_range["Тип"].dropna().unique().tolist())

    f_df = df_in_range[
        (df_in_range["Компоненты"].isin(sel_teams)) &
        (df_in_range["Резолюция"].isin(sel_res)) &
        (df_in_range["Тип"].isin(sel_types))
    ].copy()

    if f_df.empty:
        raise RuntimeError("Нет данных после фильтрации.")

    base_week_df = df[
        (df["Компоненты"].isin(sel_teams)) &
        (df["Резолюция"].isin(sel_res)) &
        (df["Тип"].isin(sel_types))
    ].copy()

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

    time_order_df = (
        f_df.groupby("Компоненты")["ttm_days"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    t_order = time_order_df["Компоненты"].tolist()

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

    t_parts_long["Метрика"] = t_parts_long["Метрика"].map({
        "cycle_time": "Cycle time",
        "wait_time_days": "Ожидание"
    })

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

    fig_a.update_layout(height=270, xaxis_title=None, yaxis_title=None, legend_title=None, margin=dict(l=40, r=20, t=10, b=10))

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
    fig_l.update_layout(height=270, xaxis_title=None, yaxis_title=None, showlegend=False, margin=dict(l=40, r=20, t=10, b=10))

    daily_df = f_df.set_index("Дата создания").resample("D").size().reset_index(name="Задач")
    weekend_df = daily_df[daily_df["Дата создания"].dt.weekday.isin([5, 6])].copy()

    fig_d = px.line(daily_df, x="Дата создания", y="Задач", markers=True, color_discrete_sequence=["#6244BB"], template="plotly_white")
    fig_d.update_traces(
        visible=True,
        line=dict(color="#6244BB"),
        marker=dict(color="#6244BB", size=7),
        hovertemplate="Дата: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>"
    )
    fig_d.add_scatter(
        x=weekend_df["Дата создания"],
        y=weekend_df["Задач"],
        mode="markers",
        visible=True,
        marker=dict(color="#E45757", size=8, line=dict(color="white", width=1)),
        hovertemplate="Выходной<br>Дата: %{x|%d.%m.%Y}<br>Задач: %{y}<extra></extra>"
    )
    fig_d.update_layout(height=250, xaxis_title=None, yaxis_title=None, margin=dict(l=20, r=20, t=8, b=10), showlegend=False)

    dist_df = f_df[["cycle_time", "wait_time_days"]].dropna().copy()
    dist_long = dist_df.melt(value_vars=["cycle_time", "wait_time_days"], var_name="Метрика", value_name="Дни")
    dist_long["Метрика"] = dist_long["Метрика"].replace({"cycle_time": "Cycle Time", "wait_time_days": "Ожидание"})
    fig_dist = px.histogram(
        dist_long,
        x="Дни",
        color="Метрика",
        barmode="overlay",
        nbins=20,
        opacity=0.65,
        color_discrete_map={"Cycle Time": "#6244BB", "Ожидание": "#A485E0"},
        template="plotly_white"
    )
    fig_dist.update_layout(height=250, xaxis_title="Дни", yaxis_title="Количество задач", legend_title=None, margin=dict(l=20, r=20, t=20, b=10))

    contacts_dist = f_df["Количество обращений"].value_counts(dropna=False).reset_index()
    contacts_dist.columns = ["Количество обращений", "Кол-во"]
    cat_order = ["1-4", "5-10", "11-100", "100+"]
    contacts_dist["Количество обращений"] = pd.Categorical(contacts_dist["Количество обращений"], categories=cat_order, ordered=True)
    contacts_dist = contacts_dist.sort_values("Количество обращений")

    fig_contacts = px.pie(
        contacts_dist,
        names="Количество обращений",
        values="Кол-во",
        hole=0.6,
        color="Количество обращений",
        color_discrete_map={"1-4": "#5B3FC4", "5-10": "#8C6FF0", "11-100": "#B9A3FA", "100+": "#E1D8FF"},
        template="plotly_white"
    )
    fig_contacts.update_traces(textinfo="percent", textfont_size=12)
    fig_contacts.update_layout(height=250, margin=dict(l=20, r=20, t=15, b=15), legend_title=None, showlegend=True, font=dict(size=11))

    total_tasks = len(f_df)
    ttm_avg = f_df["ttm_days"].mean() if len(f_df) else 0.0
    ttm_med = f_df["ttm_days"].median() if len(f_df) else 0.0
    cycle_avg = f_df["cycle_time"].mean() if len(f_df) else 0.0
    cycle_med = f_df["cycle_time"].median() if len(f_df) else 0.0
    wait_avg = f_df["wait_time_days"].mean() if len(f_df) else 0.0
    wait_med = f_df["wait_time_days"].median() if len(f_df) else 0.0
    later_pct = ((f_df["Резолюция"] == "Позже").mean() * 100) if len(f_df) else 0.0
    active_pct = ((f_df["cycle_time"].sum() / f_df["ttm_days"].sum()) * 100) if f_df["ttm_days"].sum() > 0 else 0.0
    pingpong_avg = f_df["Пинг-понг обращения"].mean() if len(f_df) else 0.0
    pingpong_med = f_df["Пинг-понг обращения"].median() if len(f_df) else 0.0
    period_label = f"{start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}"

    overview_png = build_general_overview_png(
        period_label=period_label,
        total_tasks=total_tasks,
        ttm_avg=ttm_avg,
        ttm_med=ttm_med,
        cycle_avg=cycle_avg,
        cycle_med=cycle_med,
        wait_avg=wait_avg,
        wait_med=wait_med,
        later_pct=later_pct,
        active_pct=active_pct,
        pingpong_avg=pingpong_avg,
        pingpong_med=pingpong_med,
        fig_a=fig_a,
        fig_l=fig_l,
        fig_d=fig_d,
        fig_dist=fig_dist,
        fig_contacts=fig_contacts
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    upload_bytes_to_yadisk(overview_png, f"{REMOTE_REPORTS_FOLDER}/overview_{ts}.png")

    if weekly_ready:
        team_order_week = (
            pd.concat([current_week_df["Компоненты"], previous_week_df["Компоненты"]])
            .dropna()
            .value_counts()
            .index
            .tolist()
        )

        curr_cnt_team = current_week_df.groupby("Компоненты").size().reset_index(name="Текущая неделя")
        prev_cnt_team = previous_week_df.groupby("Компоненты").size().reset_index(name="Предыдущая неделя")
        cnt_cmp = pd.merge(curr_cnt_team, prev_cnt_team, on="Компоненты", how="outer").fillna(0)
        cnt_long = cnt_cmp.melt(id_vars="Компоненты", value_vars=["Текущая неделя", "Предыдущая неделя"], var_name="Период", value_name="Кол-во задач")
        fig_cnt_compare = px.bar(
            cnt_long,
            x="Компоненты",
            y="Кол-во задач",
            color="Период",
            barmode="group",
            text_auto=".0f",
            category_orders={"Компоненты": team_order_week},
            color_discrete_map={"Текущая неделя": "#6244BB", "Предыдущая неделя": "#D6CCFF"},
            template="plotly_white"
        )
        fig_cnt_compare.update_layout(height=250, xaxis_title=None, yaxis_title="Кол-во задач", legend_title=None, margin=dict(l=20, r=20, t=15, b=10))

        curr_ttm_team = current_week_df.groupby("Компоненты")["ttm_days"].mean().reset_index(name="Текущая неделя")
        prev_ttm_team = previous_week_df.groupby("Компоненты")["ttm_days"].mean().reset_index(name="Предыдущая неделя")
        ttm_cmp = pd.merge(curr_ttm_team, prev_ttm_team, on="Компоненты", how="outer").fillna(0)
        ttm_long = ttm_cmp.melt(id_vars="Компоненты", value_vars=["Текущая неделя", "Предыдущая неделя"], var_name="Период", value_name="TTM")
        fig_ttm_compare = px.bar(
            ttm_long,
            x="Компоненты",
            y="TTM",
            color="Период",
            barmode="group",
            text_auto=".2f",
            category_orders={"Компоненты": team_order_week},
            color_discrete_map={"Текущая неделя": "#6244BB", "Предыдущая неделя": "#D6CCFF"},
            template="plotly_white"
        )
        fig_ttm_compare.update_layout(height=250, xaxis_title=None, yaxis_title="TTM, дней", legend_title=None, margin=dict(l=20, r=20, t=15, b=10))

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
        fig_flow = px.line(
            weekly_flow,
            x="X",
            y="Задач",
            color="Период",
            markers=True,
            category_orders={"X": x_labels},
            color_discrete_map={"Текущая неделя": "#6244BB", "Предыдущая неделя": "#D6CCFF"},
            template="plotly_white"
        )
        fig_flow.update_layout(height=230, xaxis_title=None, yaxis_title="Кол-во задач", legend_title=None, margin=dict(l=20, r=20, t=15, b=10))

        curr_contacts = current_week_df["Количество обращений"].value_counts().reindex(cat_order, fill_value=0).reset_index()
        curr_contacts.columns = ["Количество обращений", "Кол-во"]
        curr_contacts["Период"] = "Текущая неделя"

        prev_contacts = previous_week_df["Количество обращений"].value_counts().reindex(cat_order, fill_value=0).reset_index()
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
            color_discrete_map={"Текущая неделя": "#6244BB", "Предыдущая неделя": "#D6CCFF"},
            template="plotly_white"
        )
        fig_contacts_compare.update_layout(height=230, xaxis_title=None, yaxis_title="Кол-во задач", legend_title=None, margin=dict(l=20, r=20, t=15, b=10))

        current_label = f"{cw_start.strftime('%d.%m.%Y')} — {cw_end.strftime('%d.%m.%Y')}"
        previous_label = f"{pw_start.strftime('%d.%m.%Y')} — {pw_end.strftime('%d.%m.%Y')}"

        weekly_png = build_weekly_compare_png(
            current_label=current_label,
            previous_label=previous_label,
            current_metrics=current_metrics,
            previous_metrics=previous_metrics,
            fig_cnt_compare=fig_cnt_compare,
            fig_ttm_compare=fig_ttm_compare,
            fig_flow=fig_flow,
            fig_contacts_compare=fig_contacts_compare
        )
        upload_bytes_to_yadisk(weekly_png, f"{REMOTE_REPORTS_FOLDER}/weekly_compare_{ts}.png")

    print("PNG-отчёты загружены на Яндекс Диск.")


if __name__ == "__main__":
    main()
