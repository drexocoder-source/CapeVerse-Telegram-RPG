import os

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.parser.parser import Parser

from database.mongo import init_db
from handlers.admin import register as register_admin
from handlers.player import register


def create_bot() -> Client | None:
    bot_token = os.getenv("BOT_TOKEN", "")
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    if not bot_token or not api_id or not api_hash:
        return None
    if not getattr(Parser.parse, "_capeverse_compat", False):
        original_parse = Parser.parse

        async def parse_compat(parser, text, mode=None):
            if isinstance(mode, str) and mode.lower() == "html":
                mode = ParseMode.HTML
            return await original_parse(parser, text, mode)

        parse_compat._capeverse_compat = True
        Parser.parse = parse_compat
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