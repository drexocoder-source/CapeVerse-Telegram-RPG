import os

from database.mongo import get_profile


LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "-1003692127639"))
OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0") or 0)


async def log_event(client, event: str, details: str, user_id: int | None = None) -> None:
    subject = ""
    if user_id:
        profile = get_profile(user_id) or {}
        first_name = profile.get("first_name") or ""
        if not first_name:
            try:
                telegram_user = await client.get_users(user_id)
                first_name = telegram_user.first_name or "Unknown"
            except Exception:
                first_name = "Unknown"
        subject = f"\nName → {first_name}\nID → <code>{user_id}</code>"
    text = f"<b>CapeVerse log</b>\n{event} → {details}{subject}"
    targets = {LOG_CHAT_ID}
    if OWNER_ID:
        targets.add(OWNER_ID)
    for target in targets:
        try:
            await client.send_message(target, text, parse_mode="html")
        except Exception as exc:
            print(f"Audit delivery failed for {target}: {exc}")