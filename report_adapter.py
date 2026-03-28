import os
from io import BytesIO

from pypdf import PdfReader, PdfWriter

from report_payload_builder import build_last_week_report_payloads
from export_utils import build_overview_export_pdf, build_weekly_export_pdf


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
    postgres_url = os.getenv("POSTGRES_URL", "")
    if not postgres_url:
        raise RuntimeError("Не найден POSTGRES_URL.")

    payload = build_last_week_report_payloads(postgres_url=postgres_url)

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
