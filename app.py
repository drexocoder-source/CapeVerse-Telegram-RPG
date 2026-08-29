import os

from pyrogram import Client

from database.mongo import init_db
from handlers.admin import register as register_admin
from handlers.player import register


def create_bot() -> Client | None:
    bot_token = os.getenv("BOT_TOKEN", "")
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    if not bot_token or not api_id or not api_hash:
        return None
    client = Client(
        "capeverse_bot",
        api_id=int(api_id),
        api_hash=api_hash,
        bot_token=bot_token,
        in_memory=True,
    )
    register_admin(client)
    register(client)
    return client


def run_bot() -> None:
    try:
        init_db()
    except Exception as exc:
        print(f"CapeVerse database setup is incomplete: {exc}")
        return
    client = create_bot()
    if client is None:
        print("CapeVerse bot setup is incomplete. Add BOT_TOKEN, API_ID, and API_HASH.")
        return
    print("CapeVerse Kurigram bot is starting.")
    client.run()


if __name__ == "__main__":
    run_bot()