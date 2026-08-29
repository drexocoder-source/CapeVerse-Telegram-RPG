import os


LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "-1003692127639"))
OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0") or 0)


async def log_event(client, event: str, details: str, user_id: int | None = None) -> None:
    subject = f"\nUser → <code>{user_id}</code>" if user_id else ""
    text = f"<b>CapeVerse log</b>\n{event} → {details}{subject}"
    targets = {LOG_CHAT_ID}
    if OWNER_ID:
        targets.add(OWNER_ID)
    for target in targets:
        try:
            await client.send_message(target, text, parse_mode="html")
        except Exception as exc:
            print(f"Audit delivery failed for {target}: {exc}")