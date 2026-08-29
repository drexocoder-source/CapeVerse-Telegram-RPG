import asyncio
import os
import re
from typing import Any
from urllib.parse import urlparse

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.mongo import (
    add_submission,
    delete_content_wizard,
    get_content_wizard,
    list_moderators,
    save_content_wizard,
)
from plugins.ai_content import generate_character_blueprint
from utils.audit import log_event


OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0") or 0)

OPTIONS = {
    "source": ["CapeVerse Original", "Original Indian-Inspired", "Independent Creator", "Licensed Marvel", "Licensed DC", "Licensed X-Men"],
    "rights_status": ["approved", "unverified"],
    "role": ["Attacker", "Defender", "Controller", "Support", "Specialist"],
    "rarity": ["Common", "Rare", "Epic", "Legendary", "Mythic"],
    "alignment": ["Hero", "Vigilante", "Antihero"],
    "starter": ["Yes", "No"],
    "starter_origin": ["Enhanced", "Tech", "Mystic"],
    "enemy_type": ["normal", "villain", "event_boss"],
    "enemy_role": ["Brute", "Assassin", "Controller", "Support", "Boss"],
    "universe": ["MCU", "DCU", "Bhoomi-1", "CapeVerse", "Other / new"],
    "origin_type": ["Human", "Enhanced Human", "Tech-Enhanced", "Mystic", "Alien", "Other / new"],
    "ai_assist": ["Generate with AI", "Enter moves manually"],
}

HERO_STEPS = [
    {"field": "name", "title": "Hero name", "prompt": "What is the hero’s public name?"},
    {"field": "codename", "title": "Codename", "prompt": "What title or codename appears below the name?"},
    {"field": "origin_type", "title": "Character type", "options": OPTIONS["origin_type"]},
    {"field": "universe", "title": "Universe", "options": OPTIONS["universe"]},
    {"field": "place", "title": "City or place", "prompt": "Type any city, district, planet, realm, or other place name."},
    {"field": "faction", "title": "Faction", "prompt": "Which faction or team does the hero belong to?"},
    {"field": "image_url", "title": "Image URL", "prompt": "Send the Telegraph image URL from @vTelegraphBot.\nIt must begin with https://telegra.ph/ or https://graph.org/"},
    {"field": "source", "title": "Source", "options": OPTIONS["source"]},
    {"field": "rights_status", "title": "Rights status", "options": OPTIONS["rights_status"]},
    {"field": "role", "title": "Battle role", "options": OPTIONS["role"]},
    {"field": "rarity", "title": "Rarity", "options": OPTIONS["rarity"]},
    {"field": "alignment", "title": "Alignment", "options": OPTIONS["alignment"]},
    {"field": "description", "title": "Story", "prompt": "Write a detailed original description. The AI can analyze it to create balanced moves."},
    {"field": "ai_assist", "title": "Move creation", "options": OPTIONS["ai_assist"]},
    {"field": "normal_moves", "title": "Normal moves", "conditional": "manual_moves", "prompt": "Send 1–3 normal moves, one per line:\nName | Description | Damage | Unlock level | Cooldown | Effect\n\nExample:\nPulse Jab | Fast energy strike | 18 | 1 | 0 | none"},
    {"field": "defense_moves", "title": "Defense moves", "conditional": "manual_moves", "prompt": "Send 1–3 defense moves, one per line:\nName | Description | Damage | Unlock level | Cooldown | Effect\n\nDamage may be 0. Example effect → shield 35%."},
    {"field": "special_moves", "title": "Special moves", "conditional": "manual_moves", "prompt": "Send 1–3 special moves, one per line:\nName | Description | Damage | Unlock level | Cooldown | Effect\n\nUse higher unlock levels for stronger moves."},
    {"field": "starter", "title": "Add as starter?", "options": OPTIONS["starter"]},
    {"field": "starter_origin", "title": "Starter Origin", "options": OPTIONS["starter_origin"], "conditional": "starter_yes"},
]

VILLAIN_STEPS = [
    {"field": "name", "title": "Enemy name", "prompt": "What is the enemy or villain’s name?"},
    {"field": "origin_type", "title": "Character type", "options": OPTIONS["origin_type"]},
    {"field": "universe", "title": "Universe", "options": OPTIONS["universe"]},
    {"field": "place", "title": "City or place", "prompt": "Type any city, district, planet, realm, or other place name."},
    {"field": "faction", "title": "Faction", "prompt": "Which faction or force does this enemy serve?"},
    {"field": "image_url", "title": "Image URL", "prompt": "Send the Telegraph image URL from @vTelegraphBot.\nIt must begin with https://telegra.ph/ or https://graph.org/"},
    {"field": "source", "title": "Source", "options": OPTIONS["source"]},
    {"field": "rights_status", "title": "Rights status", "options": OPTIONS["rights_status"]},
    {"field": "enemy_type", "title": "Enemy type", "options": OPTIONS["enemy_type"]},
    {"field": "rarity", "title": "Rarity", "options": OPTIONS["rarity"]},
    {"field": "role", "title": "Battle role", "options": OPTIONS["enemy_role"]},
    {"field": "description", "title": "Story", "prompt": "Write a detailed original description. The AI can analyze it to build moves and difficulty."},
    {"field": "ai_assist", "title": "Move creation", "options": OPTIONS["ai_assist"]},
    {"field": "hp", "title": "Health", "conditional": "manual_stats", "prompt": "Enter total HP from 20 to 5000.", "number": (20, 5000)},
    {"field": "attack", "title": "Attack", "conditional": "manual_stats", "prompt": "Enter base attack from 1 to 500.", "number": (1, 500)},
    {"field": "min_level", "title": "Minimum player level", "conditional": "manual_stats", "prompt": "At which player level may this enemy begin appearing? Use 1–50.", "number": (1, 50)},
    {"field": "max_level", "title": "Maximum player level", "conditional": "manual_stats", "prompt": "Up to which player level may this enemy appear? Use 1–100.", "number": (1, 100)},
    {"field": "normal_moves", "title": "Normal moves", "conditional": "manual_moves", "prompt": "Send 1–3 normal moves, one per line:\nName | Description | Damage | Unlock level | Cooldown | Effect"},
    {"field": "defense_moves", "title": "Defense moves", "conditional": "manual_moves", "prompt": "Send 1–3 defense moves, one per line:\nName | Description | Damage | Unlock level | Cooldown | Effect"},
    {"field": "special_moves", "title": "Special moves", "conditional": "manual_moves", "prompt": "Send 1–3 special moves, one per line:\nName | Description | Damage | Unlock level | Cooldown | Effect"},
    {"field": "nemesis_hero_key", "title": "Nemesis hero", "prompt": "Send the linked hero key, or send None."},
]


def _allowed(user_id: int, permission: str) -> bool:
    if OWNER_ID and user_id == OWNER_ID:
        return True
    for moderator in list_moderators():
        if moderator.get("telegram_id") == user_id:
            return permission in moderator.get("permissions", [])
    return False


def _steps(kind: str) -> list[dict[str, Any]]:
    return HERO_STEPS if kind == "hero" else VILLAIN_STEPS


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return value[:40] or "unnamed"


def _valid_image_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and parsed.netloc.lower() in {"telegra.ph", "graph.org"} and bool(parsed.path.strip("/"))
    except Exception:
        return False


def _option_markup(options: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for index in range(0, len(options), 2):
        rows.append([
            InlineKeyboardButton(label, callback_data=f"wizard:pick:{_slug(label)}")
            for label in options[index:index + 2]
        ])
    rows.append([InlineKeyboardButton("Cancel", callback_data="wizard:cancel")])
    return InlineKeyboardMarkup(rows)


def _cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Cancel creation", callback_data="wizard:cancel")]])


def _current_step(wizard: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
    steps = _steps(wizard["kind"])
    index = int(wizard.get("step", 0))
    while index < len(steps):
        step = steps[index]
        if step.get("conditional") == "starter_yes" and wizard.get("payload", {}).get("starter") != "Yes":
            index += 1
            continue
        if step.get("conditional") == "manual_moves" and wizard.get("payload", {}).get("ai_assist") == "Generate with AI":
            index += 1
            continue
        if step.get("conditional") == "manual_stats" and wizard.get("payload", {}).get("ai_assist") == "Generate with AI":
            index += 1
            continue
        return index, step
    return index, None


def parse_move_lines(value: str, category: str) -> list[dict[str, Any]]:
    moves: list[dict[str, Any]] = []
    for raw_line in value.splitlines():
        line = raw_line.strip().lstrip("•-0123456789. ")
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            raise ValueError("Each move needs Name | Description | Damage.")
        try:
            damage = int(parts[2])
            unlock_level = int(parts[3]) if len(parts) > 3 and parts[3] else 1
            cooldown = int(parts[4]) if len(parts) > 4 and parts[4] else 0
        except ValueError as exc:
            raise ValueError("Damage, unlock level, and cooldown must be whole numbers.") from exc
        if not 0 <= damage <= 1000:
            raise ValueError("Move damage must be from 0 to 1000.")
        if not 1 <= unlock_level <= 50:
            raise ValueError("Unlock level must be from 1 to 50.")
        if not 0 <= cooldown <= 10:
            raise ValueError("Cooldown must be from 0 to 10.")
        moves.append({
            "name": parts[0][:80],
            "description": parts[1][:500],
            "damage": damage,
            "unlock_level": unlock_level,
            "cooldown": cooldown,
            "effect": (parts[5] if len(parts) > 5 else "none")[:200],
            "category": category,
        })
    if not 1 <= len(moves) <= 3:
        raise ValueError("Send between 1 and 3 moves in this section.")
    return moves


def _apply_move_compatibility(payload: dict[str, Any]) -> None:
    move_sets = payload.get("move_sets", {})
    normal = (move_sets.get("normal") or [{}])[0]
    defense = (move_sets.get("defense") or [{}])[0]
    special = (move_sets.get("special") or [{}])[0]
    payload["ability_signature"] = normal.get("name", "Basic Strike")
    payload["signature_damage"] = int(normal.get("damage", 12))
    payload["ability_utility"] = defense.get("name", "Guard")
    payload["utility_damage"] = int(defense.get("damage", 0))
    payload["ability_ultimate"] = special.get("name", "Special Move")
    payload["ultimate_damage"] = int(special.get("damage", 25))


def _moves_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for category in ("normal", "defense", "special"):
        moves = payload.get("move_sets", {}).get(category, [])
        lines.append(f"\n<b>{category.title()} moves</b>")
        for move in moves:
            lines.append(
                f"· {move.get('name')} · {move.get('damage', 0)} damage · "
                f"Lv {move.get('unlock_level', 1)} · CD {move.get('cooldown', 0)}"
            )
    return "\n".join(lines)


async def _prompt(message, wizard: dict[str, Any], edit: bool = False) -> None:
    index, step = _current_step(wizard)
    if step is None:
        await _preview(message, wizard, edit)
        return
    if index != wizard.get("step"):
        wizard = save_content_wizard(
            wizard["telegram_id"], wizard["kind"], index, wizard.get("payload", {}), wizard.get("first_name", "")
        )
    total = len(_steps(wizard["kind"]))
    custom_field = wizard.get("payload", {}).get("_custom_field")
    custom_prompt = (
        f"Send the new {step['title'].lower()} name."
        if custom_field == step["field"]
        else step.get("prompt", "Choose one option →")
    )
    text = f"<b>Add {wizard['kind']} · {index + 1}/{total}</b>\n\n<b>{step['title']}</b>\n{custom_prompt}"
    markup = _cancel_markup() if custom_field == step["field"] else _option_markup(step["options"]) if step.get("options") else _cancel_markup()
    if edit:
        await message.edit_text(text, parse_mode="html", reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="html", reply_markup=markup)


def _preview_text(wizard: dict[str, Any]) -> str:
    p = wizard.get("payload", {})
    if wizard["kind"] == "hero":
        starter = p.get("starter_origin", "No") if p.get("starter") == "Yes" else "No"
        return (
            "<b>Hero draft ready</b>\n\n"
            f"<b>{p.get('name')}</b> · {p.get('codename')}\n"
            f"{p.get('origin_type')} · {p.get('rarity')} · {p.get('role')} · {p.get('alignment')}\n"
            f"Universe → {p.get('universe')}\nPlace → {p.get('place')}\nFaction → {p.get('faction')}\n"
            f"Starter → {starter}\n\n"
            f"{_moves_text(p)}\n\n"
            f"Source → {p.get('source')}\nRights → {p.get('rights_status')}\n"
            "Submit this draft for owner approval?"
        )
    return (
        "<b>Enemy draft ready</b>\n\n"
        f"<b>{p.get('name')}</b> · {p.get('enemy_type')}\n"
        f"{p.get('origin_type')} · {p.get('rarity')} · {p.get('role')}\n"
        f"Universe → {p.get('universe')}\nPlace → {p.get('place')}\nFaction → {p.get('faction')}\n"
        f"HP → {p.get('hp')} · Attack → {p.get('attack')}\n"
        f"Appears → player levels {p.get('min_level', 1)}–{p.get('max_level', 100)}\n"
        f"{_moves_text(p)}\n"
        f"Nemesis hero → {p.get('nemesis_hero_key')}\n\n"
        f"Source → {p.get('source')}\nRights → {p.get('rights_status')}\n"
        "Submit this draft for owner approval?"
    )


async def _preview(message, wizard: dict[str, Any], edit: bool = False) -> None:
    text = _preview_text(wizard)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Submit for approval →", callback_data="wizard:submit")],
        [InlineKeyboardButton("Cancel", callback_data="wizard:cancel")],
    ])
    image_url = wizard.get("payload", {}).get("image_url")
    if image_url:
        try:
            if edit:
                await message.edit_text("<b>Draft complete</b>\n\nImage and final review →", parse_mode="html")
            await message.reply_photo(photo=image_url, caption=text, parse_mode="html", reply_markup=markup)
            return
        except Exception:
            text += "\n\n<i>Image preview unavailable; URL will still be stored.</i>"
    if edit and not getattr(message, "photo", None):
        await message.edit_text(text, parse_mode="html", reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="html", reply_markup=markup)


async def start_wizard(client, message, kind: str) -> None:
    permission = "submit_heroes" if kind == "hero" else "manage_enemies"
    if not _allowed(message.from_user.id, permission):
        return
    first_name = getattr(message.from_user, "first_name", "") or "Admin"
    existing = get_content_wizard(message.from_user.id)
    if existing and existing.get("kind") == kind:
        wizard = existing
        await message.reply_text("<b>Draft resumed</b>\n\nContinuing from your last unanswered step →", parse_mode="html")
    else:
        wizard = save_content_wizard(message.from_user.id, kind, 0, {}, first_name)
        await log_event(client, "Content wizard", f"{first_name} started a {kind} draft", message.from_user.id)
    await _prompt(message, wizard)


async def hero_command(client, message):
    await start_wizard(client, message, "hero")


async def villain_command(client, message):
    await start_wizard(client, message, "villain")


async def cancel_command(client, message):
    wizard = get_content_wizard(message.from_user.id)
    if not wizard:
        return
    delete_content_wizard(message.from_user.id)
    await message.reply_text("<b>Creation cancelled</b>\n\nNo draft was submitted.", parse_mode="html")
    await log_event(client, "Content wizard", f"{wizard.get('kind')} draft cancelled", message.from_user.id)


async def wizard_text(client, message):
    wizard = get_content_wizard(message.from_user.id)
    if not wizard or (message.text or "").startswith("/"):
        return
    index, step = _current_step(wizard)
    if not step:
        return
    payload = dict(wizard.get("payload", {}))
    custom_field = payload.get("_custom_field")
    if step.get("options") and custom_field != step["field"]:
        return
    value = (message.text or "").strip()
    if len(value) < 1 or len(value) > 1000:
        await message.reply_text("<b>Invalid answer</b>\n\nUse between 1 and 1000 characters.", parse_mode="html")
        return
    if step["field"] == "image_url" and not _valid_image_url(value):
        await message.reply_text(
            "<b>Invalid image URL</b>\n\nSend the direct Telegraph URL from @vTelegraphBot.\nAccepted → https://telegra.ph/... or https://graph.org/...",
            parse_mode="html",
        )
        return
    if step["field"] in {"normal_moves", "defense_moves", "special_moves"}:
        category = step["field"].replace("_moves", "")
        try:
            moves = parse_move_lines(value, category)
        except ValueError as exc:
            await message.reply_text(
                f"<b>Invalid move list</b>\n\n{exc}\n\nUse one move per line with | separators.",
                parse_mode="html",
            )
            return
        move_sets = dict(payload.get("move_sets", {}))
        move_sets[category] = moves
        payload["move_sets"] = move_sets
        value = moves
    if step.get("number"):
        try:
            number = int(value)
        except ValueError:
            await message.reply_text("<b>Invalid number</b>\n\nSend a whole number.", parse_mode="html")
            return
        low, high = step["number"]
        if not low <= number <= high:
            await message.reply_text(f"<b>Out of range</b>\n\nUse a value from {low} to {high}.", parse_mode="html")
            return
        value = number
    if step["field"] == "max_level" and int(value) < int(payload.get("min_level", 1)):
        await message.reply_text("<b>Invalid level range</b>\n\nMaximum level must be equal to or higher than minimum level.", parse_mode="html")
        return
    payload.pop("_custom_field", None)
    payload[step["field"]] = value
    if step["field"] == "special_moves":
        _apply_move_compatibility(payload)
    wizard = save_content_wizard(message.from_user.id, wizard["kind"], index + 1, payload, wizard.get("first_name", ""))
    await _prompt(message, wizard)


async def wizard_callback(client, callback_query):
    data = callback_query.data or ""
    if not data.startswith("wizard:"):
        return
    await callback_query.answer()
    if data.startswith("wizard:start:"):
        kind = data.split(":", 2)[2]
        permission = "submit_heroes" if kind == "hero" else "manage_enemies"
        if not _allowed(callback_query.from_user.id, permission):
            return
        first_name = callback_query.from_user.first_name or "Admin"
        existing = get_content_wizard(callback_query.from_user.id)
        wizard = existing if existing and existing.get("kind") == kind else save_content_wizard(callback_query.from_user.id, kind, 0, {}, first_name)
        await _prompt(callback_query.message, wizard, edit=True)
        return
    wizard = get_content_wizard(callback_query.from_user.id)
    if not wizard:
        await callback_query.message.reply_text("<b>No active draft</b>\n\nStart again with /submithero or /submitvillain.", parse_mode="html")
        return
    if data == "wizard:cancel":
        delete_content_wizard(callback_query.from_user.id)
        await callback_query.message.edit_text("<b>Creation cancelled</b>\n\nNo draft was submitted.", parse_mode="html")
        await log_event(client, "Content wizard", f"{wizard.get('kind')} draft cancelled", callback_query.from_user.id)
        return
    if data == "wizard:submit":
        payload = dict(wizard.get("payload", {}))
        kind = wizard["kind"]
        if kind == "hero":
            payload["hero_key"] = _slug(payload["name"])
            payload["is_starter"] = payload.get("starter") == "Yes"
            payload["starter_origin"] = payload.get("starter_origin", "None")
            payload["status"] = "draft"
        else:
            payload["villain_key"] = _slug(payload["name"])
            nemesis = str(payload.get("nemesis_hero_key", "None"))
            payload["nemesis_for"] = [] if nemesis.lower() == "none" else [_slug(nemesis)]
            payload["status"] = "draft"
        _apply_move_compatibility(payload)
        submission_id = add_submission(kind, payload["name"], payload, str(callback_query.from_user.id))
        delete_content_wizard(callback_query.from_user.id)
        await callback_query.message.edit_text(
            f"<b>{kind.title()} submitted → pending</b>\n\n"
            f"{payload['name']}\nSubmission → <code>{submission_id}</code>\n"
            "The owner can review it from /pending.",
            parse_mode="html",
        )
        await log_event(
            client,
            f"New {kind}",
            f"{wizard.get('first_name') or 'Admin'} submitted {payload['name']}",
            callback_query.from_user.id,
        )
        return
    if data.startswith("wizard:pick:"):
        index, step = _current_step(wizard)
        if not step or not step.get("options"):
            return
        selected_slug = data.split(":", 2)[2]
        value = next((option for option in step["options"] if _slug(option) == selected_slug), None)
        if value is None:
            return
        payload = dict(wizard.get("payload", {}))
        if value == "Other / new":
            payload["_custom_field"] = step["field"]
            wizard = save_content_wizard(
                callback_query.from_user.id, wizard["kind"], index, payload, wizard.get("first_name", "")
            )
            await _prompt(callback_query.message, wizard, edit=True)
            return
        if step["field"] == "ai_assist" and value == "Generate with AI":
            await callback_query.message.edit_text(
                "<b>AI character designer</b>\n\nAnalyzing the description and building balanced move sets…",
                parse_mode="html",
            )
            blueprint = await asyncio.to_thread(
                generate_character_blueprint,
                str(payload.get("description", "")),
                wizard["kind"],
            )
            if not blueprint:
                value = "Enter moves manually"
                await callback_query.message.reply_text(
                    "<b>AI unavailable</b>\n\nThe manual move builder is ready instead. Your draft was not lost.",
                    parse_mode="html",
                )
            else:
                payload["move_sets"] = blueprint.get("moves", {})
                for field in ("role", "rarity", "alignment"):
                    if blueprint.get(field):
                        payload[f"ai_suggested_{field}"] = blueprint[field]
                if wizard["kind"] == "villain":
                    for field in ("hp", "attack", "min_level", "max_level"):
                        if blueprint.get(field) is not None:
                            payload[field] = blueprint[field]
                _apply_move_compatibility(payload)
        payload[step["field"]] = value
        wizard = save_content_wizard(
            callback_query.from_user.id, wizard["kind"], index + 1, payload, wizard.get("first_name", "")
        )
        await _prompt(callback_query.message, wizard, edit=True)


def register(client) -> None:
    client.add_handler(MessageHandler(hero_command, filters.command("submithero")))
    client.add_handler(MessageHandler(villain_command, filters.command("submitvillain")))
    client.add_handler(MessageHandler(cancel_command, filters.command("cancel")))
    client.add_handler(MessageHandler(wizard_text, filters.private & filters.text), group=1)
    client.add_handler(CallbackQueryHandler(wizard_callback, filters.regex(r"^wizard:")), group=1)