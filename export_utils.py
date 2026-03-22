import io
import os
from textwrap import wrap

import pandas as pd
import plotly.graph_objects as go

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


PDF_BG = HexColor("#F7F2FA")
PDF_CARD = HexColor("#FFFFFF")
PDF_BORDER = HexColor("#E6E9EF")
PDF_ACCENT = HexColor("#6244BB")
PDF_TEXT = HexColor("#1A1C1E")
PDF_SUB = HexColor("#7E8694")

PDF_FONT_REGULAR = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
PLOTLY_EXPORT_FONT = "Arial"


def setup_export_fonts():
    global PDF_FONT_REGULAR, PDF_FONT_BOLD, PLOTLY_EXPORT_FONT

    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "DejaVu Sans",
        ),
        (
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "Noto Sans",
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "Liberation Sans",
        ),
        (
            "/Library/Fonts/Arial Unicode.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "Arial Unicode MS",
        ),
        (
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "Arial",
        ),
    ]

    for regular_path, bold_path, plotly_family in candidates:
        if os.path.exists(regular_path) and os.path.exists(bold_path):
            pdfmetrics.registerFont(TTFont("ExportFont", regular_path))
            pdfmetrics.registerFont(TTFont("ExportFont-Bold", bold_path))
            PDF_FONT_REGULAR = "ExportFont"
            PDF_FONT_BOLD = "ExportFont-Bold"
            PLOTLY_EXPORT_FONT = plotly_family
            return


setup_export_fonts()


def truncate_text(text, max_len=140):
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def format_filter_line(label, values, max_len=180):
    if not values:
        return f"{label}: все"
    txt = ", ".join(map(str, values))
    return truncate_text(f"{label}: {txt}", max_len=max_len)


def format_value(val, is_percent=False, digits=2, as_int=False):
    if pd.isna(val):
        return "н/д"
    if as_int:
        return f"{int(round(val))}"
    if is_percent:
        return f"{val:.1f}%"
    return f"{val:.{digits}f}"


def delta_text(curr, prev, is_percent=False, digits=2):
    if pd.isna(curr) or pd.isna(prev):
        return "н/д"
    diff = curr - prev
    sign = "+" if diff > 0 else ""
    if is_percent:
        return f"{sign}{diff:.1f} п.п."
    return f"{sign}{diff:.{digits}f}"


def prepare_fig_for_pdf(fig):
    fig2 = go.Figure(fig)

    fig2.update_layout(
        updatemenus=[],
        sliders=[],
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(
            family=PLOTLY_EXPORT_FONT,
            size=14,
            color="#1A1C1E",
        ),
        title_font=dict(
            family=PLOTLY_EXPORT_FONT,
            size=17,
            color="#1A1C1E",
        ),
        legend_font=dict(
            family=PLOTLY_EXPORT_FONT,
            size=13,
            color="#1A1C1E",
        ),
        margin=dict(l=70, r=35, t=45, b=55),
    )

    fig2.update_xaxes(
        automargin=True,
        tickfont=dict(family=PLOTLY_EXPORT_FONT, size=13),
        title_font=dict(family=PLOTLY_EXPORT_FONT, size=14),
    )
    fig2.update_yaxes(
        automargin=True,
        tickfont=dict(family=PLOTLY_EXPORT_FONT, size=13),
        title_font=dict(family=PLOTLY_EXPORT_FONT, size=14),
    )

    fig2.update_traces(
        textfont=dict(
            family=PLOTLY_EXPORT_FONT,
            size=13,
            color="#1A1C1E",
        ),
        selector=dict(type="bar"),
    )

    fig2.update_traces(
        textfont=dict(
            family=PLOTLY_EXPORT_FONT,
            size=13,
            color="#1A1C1E",
        ),
        selector=dict(type="pie"),
    )

    return fig2


def fig_to_png_bytes(fig, width_px=1600, height_px=900, scale=2):
    fig2 = prepare_fig_for_pdf(fig)
    try:
        return fig2.to_image(
            format="png",
            width=width_px,
            height=height_px,
            scale=scale,
        )
    except Exception as e:
        raise RuntimeError(
            "Не удалось собрать PDF-экспорт. Для экспорта нужны kaleido, reportlab и браузер для kaleido."
        ) from e


def draw_round_rect(c, x, y, w, h, fill_color=PDF_CARD, stroke_color=PDF_BORDER, radius=14, stroke_width=1):
    c.setFillColor(fill_color)
    c.setStrokeColor(stroke_color)
    c.setLineWidth(stroke_width)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def draw_wrapped_text(c, text, x, y, max_chars, line_height=11, font_name=None, font_size=9, color=None):
    if font_name:
        c.setFont(font_name, font_size)
    if color:
        c.setFillColor(color)

    lines = wrap(str(text), width=max_chars, break_long_words=False, replace_whitespace=False)
    for line in lines:
        c.drawString(x, y, line)
        y -= line_height
    return y


def draw_page_header(c, page_w, page_h, title, subtitle_lines, page_num, total_pages):
    margin = 24
    y_top = page_h - margin

    c.setFillColor(PDF_BG)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    c.setFillColor(PDF_TEXT)
    c.setFont(PDF_FONT_BOLD, 20)
    c.drawString(margin, y_top - 14, title)

    badge_w = 78
    badge_h = 24
    badge_x = page_w - margin - badge_w
    badge_y = y_top - 26

    c.setFillColor(PDF_ACCENT)
    c.roundRect(badge_x, badge_y, badge_w, badge_h, 12, fill=1, stroke=0)

    c.setFillColor(white)
    c.setFont(PDF_FONT_BOLD, 10)
    c.drawCentredString(badge_x + badge_w / 2, badge_y + 7, f"{page_num}/{total_pages}")

    c.setFillColor(PDF_SUB)
    y = y_top - 38
    for line in subtitle_lines:
        y = draw_wrapped_text(
            c,
            line,
            margin,
            y,
            max_chars=135,
            line_height=11,
            font_name=PDF_FONT_REGULAR,
            font_size=9,
            color=PDF_SUB,
        )
        y -= 2

    c.setStrokeColor(HexColor("#D8CDF4"))
    c.setLineWidth(1)
    c.line(margin, y - 2, page_w - margin, y - 2)

    return y - 14


def draw_kpi_grid_pdf(c, page_w, y_top, cards, cols=4):
    margin = 24
    gap = 8
    card_h = 84
    usable_w = page_w - 2 * margin
    card_w = (usable_w - gap * (cols - 1)) / cols

    y = y_top

    for idx, card in enumerate(cards):
        row = idx // cols
        col = idx % cols

        row_cards = cards[row * cols:(row + 1) * cols]
        current_cols = len(row_cards)
        current_row_w = current_cols * card_w + (current_cols - 1) * gap
        start_x = margin + (usable_w - current_row_w) / 2 if current_cols < cols else margin

        x = start_x + col * (card_w + gap)
        yy = y - row * (card_h + gap) - card_h

        draw_round_rect(c, x, yy, card_w, card_h, fill_color=PDF_CARD, stroke_color=PDF_BORDER, radius=12)

        c.setFillColor(PDF_TEXT)
        c.setFont(PDF_FONT_BOLD, 9)
        c.drawString(x + 10, yy + card_h - 16, truncate_text(card["title"], 28))

        c.setFillColor(HexColor(card.get("color", "#6244BB")))
        c.setFont(PDF_FONT_BOLD, 17)
        c.drawString(x + 10, yy + card_h - 40, str(card["value"]))

        if card.get("subvalue"):
            c.setFillColor(PDF_SUB)
            c.setFont(PDF_FONT_REGULAR, 8)
            c.drawString(x + 10, yy + 10, truncate_text(card["subvalue"], 32))

    total_rows = (len(cards) + cols - 1) // cols
    return y - total_rows * card_h - (total_rows - 1) * gap - 14


def draw_chart_panel(c, x, y, w, h, title, fig):
    draw_round_rect(c, x, y, w, h, fill_color=PDF_CARD, stroke_color=PDF_BORDER, radius=14)

    c.setFillColor(PDF_TEXT)
    c.setFont(PDF_FONT_BOLD, 12)
    c.drawString(x + 12, y + h - 18, truncate_text(title, 70))

    header_h = 30
    img_pad_x = 10
    img_pad_bottom = 10

    inner_x = x + img_pad_x
    inner_y = y + img_pad_bottom
    inner_w = w - 2 * img_pad_x
    inner_h = h - header_h - img_pad_bottom - 4

    png = fig_to_png_bytes(
        fig,
        width_px=max(1600, int(inner_w * 2.8)),
        height_px=max(950, int(inner_h * 2.8)),
        scale=2,
    )

    reader = ImageReader(io.BytesIO(png))
    img_w_px, img_h_px = reader.getSize()

    scale = min(inner_w / img_w_px, inner_h / img_h_px)
    draw_w = img_w_px * scale
    draw_h = img_h_px * scale

    draw_x = inner_x + (inner_w - draw_w) / 2
    draw_y = inner_y + (inner_h - draw_h) / 2

    c.drawImage(
        reader,
        draw_x,
        draw_y,
        width=draw_w,
        height=draw_h,
        preserveAspectRatio=True,
        mask="auto",
    )


def get_two_row_chart_height(page_bottom_y, current_top_y, gap, min_height=180, max_height=285):
    available = current_top_y - page_bottom_y
    row_h = (available - gap) / 2
    return max(min_height, min(max_height, row_h))


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
