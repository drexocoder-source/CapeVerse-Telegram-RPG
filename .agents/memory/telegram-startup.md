---
name: Telegram startup
description: CapeVerse's Telegram client startup and command-menu registration behavior
---

For CapeVerse, the Telegram command menu should be registered asynchronously after the Kurigram client has connected, rather than making bot readiness wait on the BotFather command update.

**Why:** Telegram handshakes can take longer than the web health server and can make a healthy process look stalled when command registration is awaited inline.

**How to apply:** Keep the bot's running log immediately after client connection, schedule command registration in the background, and log registration failures without preventing the bot from serving updates.