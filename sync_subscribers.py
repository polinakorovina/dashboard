import json
import os
from pathlib import Path

import requests
import yadisk

YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SECRET_CODE = os.getenv("TELEGRAM_START_CODE", "duty2026")

STATE_REMOTE_PATH = os.getenv("TELEGRAM_STATE_PATH", "/bot_state/subscribers_state.json")
STATE_LOCAL_PATH = "subscribers_state.json"

y = yadisk.YaDisk(token=YANDEX_TOKEN)


def ensure_remote_dir(remote_dir: str):
    remote_dir = remote_dir.strip()
    if not remote_dir or remote_dir == "/":
        return
    parts = [p for p in remote_dir.strip("/").split("/") if p]
    current = ""
    for part in parts:
        current += f"/{part}"
        if not y.exists(current):
            y.mkdir(current)


def load_state():
    if y.exists(STATE_REMOTE_PATH):
        if Path(STATE_LOCAL_PATH).exists():
            Path(STATE_LOCAL_PATH).unlink()
        y.download(STATE_REMOTE_PATH, STATE_LOCAL_PATH)
        with open(STATE_LOCAL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "last_update_id": 0,
        "subscribers": []
    }


def save_state(state):
    with open(STATE_LOCAL_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    folder = os.path.dirname(STATE_REMOTE_PATH)
    ensure_remote_dir(folder)

    if y.exists(STATE_REMOTE_PATH):
        y.remove(STATE_REMOTE_PATH, permanently=True)

    y.upload(STATE_LOCAL_PATH, STATE_REMOTE_PATH)


def get_updates(offset: int):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    resp = requests.get(
        url,
        params={"offset": offset, "timeout": 0},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data["result"]


def add_subscriber(state, chat_id, chat_type, title=None):
    subscribers = state["subscribers"]
    if not any(s["chat_id"] == chat_id for s in subscribers):
        subscribers.append({
            "chat_id": chat_id,
            "chat_type": chat_type,
            "title": title or ""
        })


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=60)
    resp.raise_for_status()


def process_message(state, message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    title = chat.get("title", "")
    text = message.get("text", "") or ""

    # Личка: /start <код>
    if chat_type == "private":
        parts = text.strip().split(maxsplit=1)
        if parts and parts[0] == "/start":
            start_param = parts[1].strip() if len(parts) > 1 else ""
            if start_param == SECRET_CODE:
                add_subscriber(state, chat_id, chat_type, title)
                send_message(chat_id, "Доступ открыт. Вы будете получать еженедельный отчёт.")
            else:
                send_message(chat_id, "Доступ ограничен.")

    # Группа: /register <код>
    elif chat_type in ("group", "supergroup"):
        parts = text.strip().split(maxsplit=1)
        if parts and parts[0].startswith("/register"):
            code = parts[1].strip() if len(parts) > 1 else ""
            if code == SECRET_CODE:
                add_subscriber(state, chat_id, chat_type, title)
                send_message(chat_id, "Группа подключена к еженедельной рассылке.")
            else:
                send_message(chat_id, "Неверный код доступа.")


def main():
    if not YANDEX_TOKEN or not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не заданы YANDEX_TOKEN или TELEGRAM_BOT_TOKEN")

    if not y.check_token():
        raise RuntimeError("YANDEX_TOKEN невалидный")

    state = load_state()
    offset = state.get("last_update_id", 0) + 1

    updates = get_updates(offset)

    max_update_id = state.get("last_update_id", 0)

    for upd in updates:
        update_id = upd["update_id"]
        max_update_id = max(max_update_id, update_id)

        if "message" in upd:
            process_message(state, upd["message"])

    state["last_update_id"] = max_update_id
    save_state(state)
    print("Subscribers synced.")


if __name__ == "__main__":
    main()
