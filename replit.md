# CapeVerse

CapeVerse is a Kurigram-powered Telegram superhero collection RPG with MongoDB persistence, clean symbol-led messaging, a generated player guide, and bot-based owner controls.

## Run & Operate

- `python run.py` — run the Flask welcome endpoint and Kurigram bot
- `python web.py` — run only the text welcome endpoint
- `python app.py` — run only the Telegram bot
- Required secrets: `BOT_TOKEN`, `API_ID`, `API_HASH`, `MONGODB_URI`, `OWNER_TELEGRAM_ID`

## Stack

- Python 3.12
- Telegram: Kurigram + TgCrypto
- Web: Flask, text-only public page
- DB: MongoDB + PyMongo
- Documents: ReportLab player guide
- Profile cards: Pillow

## Where things live

- `app.py` — Kurigram entry point
- `web.py` — minimal Flask welcome endpoint
- `database/` — MongoDB persistence, indexes, and seed content
- `handlers/` — player and owner/moderator Telegram handlers
- `plugins/` — battle, recruitment, missions, Arena, and Rift systems
- `utils/` — Telegram formatting and generated profile cards
- `guide.py` — generated PDF player guide

## Architecture decisions

- Administration stays inside the Telegram bot; Flask exposes only plain welcome/health text.
- Published heroes require approved rights status.
- Player-facing messages favor arrows, typography, and short separators over borders or heavy emoji.
- MongoDB is the source of truth for players, content, teams, battles, permissions, and economy ledger entries.

## Product

- Origin onboarding and starter hero grant
- Generated guide and player profile image card
- Three-hero teams and universe synergy
- Recruitment Beacon with Signal Boost
- Patrols and Case Files
- Asynchronous Arena battles
- Rift floors and boss encounters
- Bot-based owner approval and per-command moderator permissions

## User preferences

- Keep Flask limited to a simple text welcome page.
- Keep all owner, moderator, and game administration inside the Python Telegram bot.
- Use mostly clean text symbols and arrows; use few emojis, especially in PvE and PvP.

## Gotchas

- Kurigram imports through the `pyrogram` Python namespace; do not add the upstream `Pyrogram` package to requirements.
- Keep `MONGODB_URI` and Telegram credentials in secrets only.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
