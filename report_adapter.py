import pandas as pd
from io import BytesIO

from pypdf import PdfReader, PdfWriter

from data_pipeline import read_dashboard_from_postgres
from export_utils import build_overview_export_pdf, build_weekly_export_pdf
from report_payload_builder import build_report_payloads_for_period


def merge_pdf_bytes(pdf_parts: list[bytes]) -> bytes:
    writer = PdfWriter()

    for part in pdf_parts:
        reader = PdfReader(BytesIO(part))
        for page in reader.pages:
            writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    out.seek(0)
    return out.getvalue()


def build_weekly_report_pdf_bytes() -> bytes:
    import os

    postgres_url = os.getenv("POSTGRES_URL", "")
    if not postgres_url:
        raise RuntimeError("Не найден POSTGRES_URL")

    df = read_dashboard_from_postgres(postgres_url)
    if df.empty:
        raise RuntimeError("Данные дашборда пустые.")

    if "Дата создания" not in df.columns:
        raise RuntimeError("В данных нет колонки 'Дата создания'")

    db_max = df["Дата создания"].max().date()
    start_date = db_max - pd.Timedelta(days=6)
    start_date = start_date.date() if hasattr(start_date, "date") else start_date
    end_date = db_max

    payload = build_report_payloads_for_period(start_date, end_date, postgres_url=postgres_url)

    overview_pdf = build_overview_export_pdf(
        bundle=payload["overview_bundle"],
        start_date=payload["start_date"],
        end_date=payload["end_date"],
        sel_teams=payload["sel_teams"],
        sel_res=payload["sel_res"],
        sel_types=payload["sel_types"],
    )

    weekly_pdf = build_weekly_export_pdf(
        bundle=payload["weekly_bundle"],
        sel_teams=payload["sel_teams"],
        sel_res=payload["sel_res"],
        sel_types=payload["sel_types"],
    )

    return merge_pdf_bytes([overview_pdf, weekly_pdf])
