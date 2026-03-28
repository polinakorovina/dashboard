import io
import json
import os
from pathlib import Path

import fitz
import requests
import yadisk

from report_adapter import build_weekly_report_pdf_bytes

YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "")

STATE_REMOTE_PATH = os.getenv("TELEGRAM_STATE_PATH", "/bot_state/subscribers_state.json")
STATE_LOCAL_PATH = "subscribers_state.json"


def download_state(y):
    if not y.exists(STATE_REMOTE_PATH):
        return {"subscribers": []}

    local_path = Path(STATE_LOCAL_PATH)
    if local_path.exists():
        local_path.unlink()

    y.download(STATE_REMOTE_PATH, STATE_LOCAL_PATH)

    with open(STATE_LOCAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def pdf_bytes_to_png_bytes_list(pdf_bytes: bytes, scale: float = 2.0):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []

    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        images.append(pix.tobytes("png"))

    doc.close()
    return images


def build_caption():
    lines = [
        "<b>Еженедельный отчёт по дашборду дежурств</b>",
        "",
        "Во вложении — свежий отчёт за новую неделю.",
    ]

    if DASHBOARD_URL:
        lines += ["", f'<a href="{DASHBOARD_URL}">Открыть дашборд</a>']

    return "\n".join(lines)


def send_album(chat_id, image_bytes_list, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup"

    media = []
    files = {}

    for idx, img_bytes in enumerate(image_bytes_list, start=1):
        attach_name = f"photo{idx}"
        item = {
            "type": "photo",
            "media": f"attach://{attach_name}",
        }
        if idx == 1:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
        media.append(item)

        bio = io.BytesIO(img_bytes)
        bio.seek(0)
        files[attach_name] = (f"page_{idx}.png", bio, "image/png")

    data = {
        "chat_id": str(chat_id),
        "media": json.dumps(media, ensure_ascii=False),
    }

    response = requests.post(url, data=data, files=files, timeout=180)

    for _, ftuple in files.items():
        ftuple[1].close()

    if not response.ok:
        raise RuntimeError(
            f"Telegram send failed for {chat_id}: {response.status_code} {response.text}"
        )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")
    if not YANDEX_TOKEN:
        raise RuntimeError("Не задан YANDEX_TOKEN")

    y = yadisk.YaDisk(token=YANDEX_TOKEN)

    if not y.check_token():
        raise RuntimeError("YANDEX_TOKEN невалидный")

    state = download_state(y)
    subscribers = state.get("subscribers", [])
    if not subscribers:
        raise RuntimeError("Нет подписчиков для рассылки.")

    pdf_bytes = build_weekly_report_pdf_bytes()
    images = pdf_bytes_to_png_bytes_list(pdf_bytes, scale=2.0)

    if not images:
        raise RuntimeError("PDF пустой: нет страниц для отправки.")

    caption = build_caption()

    for sub in subscribers:
        chat_id = sub["chat_id"]
        try:
            send_album(chat_id, images, caption)
            print(f"Sent to {chat_id}")
        except Exception as e:
            print(f"Failed for {chat_id}: {e}")

    local_path = Path(STATE_LOCAL_PATH)
    if local_path.exists():
        local_path.unlink()


if __name__ == "__main__":
    main()
