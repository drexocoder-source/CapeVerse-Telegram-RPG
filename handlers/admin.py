import os
from typing import Any

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.mongo import (
    add_submission,
    get_hero,
    get_team,
    list_owned_heroes,
    list_moderators,
    list_heroes,
    list_submissions,
    publish_content,
    publish_event,
    publish_villain,
    review_submission,
    search_players,
    seed_hero,
    update_hero,
    upsert_moderator,
)
from handlers.content_wizard import _apply_move_compatibility, parse_move_lines, register as register_content_wizard
from plugins.battle import simulate_pve
from utils.audit import log_event
from utils.formatting import profile_text
from utils.profile_card import generate_profile_card


OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0") or 0)
PERMISSIONS = [
    "submit_heroes",
    "submit_content",
    "manage_abilities",
    "manage_missions",
    "manage_relics",
    "manage_enemies",
    "manage_events",
    "view_players",
    "view_economy",
    "publish_content",
]
pending_mod_targets: dict[int, int] = {}
pending_mod_permissions: dict[int, set[str]] = {}
pending_mod_names: dict[int, str] = {}
pending_character_edits: dict[int, dict[str, str]] = {}


def is_owner(user_id: int) -> bool:
    return OWNER_ID > 0 and user_id == OWNER_ID


def moderator_permissions(user_id: int) -> set[str]:
    for moderator in list_moderators():
        if moderator.get("telegram_id") == user_id:
            return set(moderator.get("permissions", []))
    return set()


def can(user_id: int, permission: str) -> bool:
    return is_owner(user_id) or permission in moderator_permissions(user_id)


def owner_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Pending →", callback_data="admin:pending"),
                InlineKeyboardButton("Moderators", callback_data="admin:mods"),
            ],
            [
                InlineKeyboardButton("Add hero →", callback_data="wizard:start:hero"),
                InlineKeyboardButton("Add enemy →", callback_data="wizard:start:villain"),
            ],
            [
                InlineKeyboardButton("Add event guide", callback_data="admin:event_guide"),
                InlineKeyboardButton("Add kind", callback_data="admin:kind_guide"),
            ],
            [InlineKeyboardButton("AI art rights guide", callback_data="admin:art_guide")],
        ]
    )


def permission_markup(target_id: int, selected: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for permission in PERMISSIONS:
        mark = "✓" if permission in selected else "·"
        rows.append([InlineKeyboardButton(f"{mark} {permission.replace('_', ' ')}", callback_data=f"admin:perm:{target_id}:{permission}")])
    rows.append([InlineKeyboardButton("Save moderator →", callback_data=f"admin:save_mod:{target_id}")])
    return InlineKeyboardMarkup(rows)


def pending_markup(items: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = []
    for item in items[:12]:
        item_id = str(item["_id"])
        rows.append(
            [
                InlineKeyboardButton(f"Approve {item['title'][:18]}", callback_data=f"admin:approve:{item_id}"),
                InlineKeyboardButton("Reject", callback_data=f"admin:reject:{item_id}"),
            ]
        )
    rows.append([InlineKeyboardButton("← Owner panel", callback_data="admin:home")])
    return InlineKeyboardMarkup(rows)


def character_edit_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Story", callback_data="admin:editfield:description"),
            InlineKeyboardButton("Place", callback_data="admin:editfield:place"),
        ],
        [
            InlineKeyboardButton("Character type", callback_data="admin:editfield:origin_type"),
            InlineKeyboardButton("Codename", callback_data="admin:editfield:codename"),
        ],
        [InlineKeyboardButton("Normal moves", callback_data="admin:editfield:normal")],
        [InlineKeyboardButton("Defense moves", callback_data="admin:editfield:defense")],
        [InlineKeyboardButton("Special moves", callback_data="admin:editfield:special")],
        [InlineKeyboardButton("← Owner panel", callback_data="admin:home")],
    ])


def _target_from_message(message) -> int | None:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    parts = (message.text or "").split()
    if len(parts) > 1 and parts[1].isdigit():
        return int(parts[1])
    return None


def _target_name_from_message(message) -> str:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.first_name or "Moderator"
    return "Moderator"


async def owner_command(client, message):
    if not is_owner(message.from_user.id):
        return
    await message.reply_text(
        "<b>Owner control</b>\n\n"
        "All publishing and access decisions happen here.\n"
        "Choose a tool →",
        parse_mode="html",
        reply_markup=owner_panel_markup(),
    )
    await log_event(client, "Owner verification", "Owner panel opened", message.from_user.id)


async def addmod_command(client, message):
    if not is_owner(message.from_user.id):
        return
    target_id = _target_from_message(message)
    if not target_id:
        await message.reply_text(
            "<b>Add moderator</b>\n\n"
            "Reply to the user’s message and send /addmod\n"
            "or use /addmod TELEGRAM_USER_ID.",
            parse_mode="html",
        )
        return
    pending_mod_targets[message.from_user.id] = target_id
    pending_mod_permissions[message.from_user.id] = set()
    pending_mod_names[message.from_user.id] = _target_name_from_message(message)
    await message.reply_text(
        f"<b>Moderator access</b>\n\nName → {pending_mod_names[message.from_user.id]}\nID → <code>{target_id}</code>\n"
        "Tap permissions to grant or remove them.\n"
        "Save when finished →",
        parse_mode="html",
        reply_markup=permission_markup(target_id, set()),
    )
    await log_event(client, "Admin access", f"Moderator permission editor opened for {target_id}", target_id)


async def submitevent_command(client, message):
    user_id = message.from_user.id
    if not can(user_id, "manage_events"):
        return
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2:
        await message.reply_text(
            "<b>Event submission</b>\n\n"
            "/submitevent key | Title | BossKey | Description | RewardCredits\n\n"
            "The BossKey must belong to a published event_boss or villain.",
            parse_mode="html",
        )
        return
    fields = [field.strip() for field in raw[1].split("|")]
    if len(fields) != 5 or not fields[4].isdigit():
        await message.reply_text("<b>Submission not saved</b>\n\nUse exactly 5 fields and a numeric reward.", parse_mode="html")
        return
    payload = {
        "event_key": fields[0].lower().replace(" ", "_"),
        "title": fields[1],
        "boss_key": fields[2].lower().replace(" ", "_"),
        "description": fields[3],
        "reward_credits": int(fields[4]),
        "status": "draft",
    }
    submission_id = add_submission("event", payload["title"], payload, str(user_id))
    await message.reply_text(
        f"<b>Event submitted → pending</b>\n\n{payload['title']}\nBoss → {payload['boss_key']}\nSubmission ID → <code>{submission_id}</code>",
        parse_mode="html",
    )
    await log_event(client, "New event", f"{payload['title']} → boss {payload['boss_key']}", user_id)


async def submitkind_command(client, message):
    user_id = message.from_user.id
    if not can(user_id, "submit_content"):
        return
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2:
        await message.reply_text(
            "<b>New content kind</b>\n\n"
            "/submitkind KIND | TITLE | DEFINITION\n\n"
            "Examples → universe, faction, enemy, boss, relic, mission, banner, event, currency",
            parse_mode="html",
        )
        return
    parts = [part.strip() for part in raw[1].split("|", 2)]
    if len(parts) != 3:
        await message.reply_text("<b>Submission not saved</b>\n\nUse KIND | TITLE | DEFINITION after /submitkind.", parse_mode="html")
        return
    kind, title, definition = parts
    add_submission(kind, title, {"details": definition}, str(user_id))
    await message.reply_text(f"<b>Content queued → {kind}</b>\n\n{title}\nOwner review is required.", parse_mode="html")
    await log_event(client, "New content", f"{kind} submitted → {title}", user_id)


async def adminhelp_command(client, message):
    if not (is_owner(message.from_user.id) or moderator_permissions(message.from_user.id)):
        return
    await message.reply_text(
        "<b>Admin guide</b>\n\n"
        "<b>Owner</b>\n"
        "/owner → open control panel\n"
        "Reply to a user + /addmod → grant exact permissions\n"
        "/pending → review queue\n"
        "/submithero → guided hero creation\n"
        "/submitvillain → guided enemy or villain creation\n"
        "/submitevent → create a boss event\n"
        "/test → simulate PvE damage without rewards\n"
        "/editchar CHARACTER_KEY → edit story, identity, or move categories\n"
        "/playersearch NAME_OR_ID → view a player progression card\n"
        "/cancel → cancel an active creation wizard\n"
        "/submitkind → submit a new content kind\n\n"
        "Moves are grouped into Normal, Defense, and Special lists.\n"
        "Each move stores name, description, damage, unlock level, cooldown, and effect.\n"
        "The AI option analyzes the story and proposes original balanced move sets.\n"
        "Set StarterOrigin to Enhanced, Tech, Mystic, or None.\n\n"
        "<b>Adding content</b>\n"
        "Draft → submit → rights check → owner approval → publish.\n"
        "Never replace a live hero without a version note.\n\n"
        "<b>AI artwork rights</b>\n"
        "For original heroes, use broad archetypes and new names, silhouettes, symbols, and stories.\n"
        "Do not prompt with Marvel, DC, X-Men, actor names, logos, or exact costume descriptions.\n"
        "AI output is not automatically copyright-free.\n"
        "Licensed heroes require documented permission before publish.\n\n"
        "Use /guideadmin to receive the full checklist.",
        parse_mode="html",
    )
    await log_event(client, "Admin verification", "Admin guide requested", message.from_user.id)


async def guideadmin_command(client, message):
    if not (is_owner(message.from_user.id) or moderator_permissions(message.from_user.id)):
        return
    await adminhelp_command(client, message)


async def pending_command(client, message):
    if not is_owner(message.from_user.id):
        return
    items = list_submissions("pending")
    if not items:
        await message.reply_text("<b>Approval queue</b>\n\nNothing is waiting.", parse_mode="html", reply_markup=owner_panel_markup())
        return
    text = "<b>Approval queue</b>\n\n" + "\n".join(
        f"· <b>{item['title']}</b>  →  {item['content_kind']}  →  {str(item['_id'])[:8]}" for item in items[:12]
    )
    await message.reply_text(text, parse_mode="html", reply_markup=pending_markup(items))


async def editchar_command(client, message):
    if not is_owner(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            "<b>Edit published character</b>\n\n"
            "Use <code>/editchar character_key</code>\n"
            "You can find keys with <code>/char character name</code>.",
            parse_mode="html",
        )
        return
    query = parts[1].strip().lower()
    hero = get_hero(query)
    if not hero:
        hero = next(
            (item for item in list_heroes("all") if query in {str(item.get("name", "")).lower(), str(item.get("codename", "")).lower()}),
            None,
        )
    if not hero:
        await message.reply_text("<b>Character not found</b>\n\nUse the exact character key or name.", parse_mode="html")
        return
    pending_character_edits[message.from_user.id] = {"hero_key": hero["hero_key"]}
    await message.reply_text(
        f"<b>Edit character</b>\n\n{hero.get('name')} · <code>{hero['hero_key']}</code>\n"
        "Choose the part to replace →",
        parse_mode="html",
        reply_markup=character_edit_markup(),
    )


async def playersearch_command(client, message):
    if not can(message.from_user.id, "view_players"):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            "<b>Player search</b>\n\nUse <code>/playersearch Telegram ID or first name</code>.",
            parse_mode="html",
        )
        return
    matches = search_players(parts[1])
    if not matches:
        await message.reply_text("<b>No player found</b>", parse_mode="html")
        return
    profile = matches[0]
    heroes = list_owned_heroes(profile["telegram_id"])
    team = get_team(profile["telegram_id"])
    synergy = min(15, max(0, len({hero.get("universe") for hero in team}) - 1) * 5)
    card = generate_profile_card(profile, heroes, len(team), synergy)
    await message.reply_photo(
        photo=str(card),
        caption=profile_text(profile, len(heroes), len(team), synergy) + f"\n\nID → <code>{profile['telegram_id']}</code>",
        parse_mode="html",
    )
    await log_event(client, "Player search", f"Viewed player {profile['telegram_id']}", message.from_user.id)


async def character_edit_text(client, message):
    state = pending_character_edits.get(message.from_user.id)
    if not state or not state.get("field") or (message.text or "").startswith("/"):
        return
    hero = get_hero(state["hero_key"])
    if not hero:
        pending_character_edits.pop(message.from_user.id, None)
        return
    field = state["field"]
    value = (message.text or "").strip()
    if field in {"normal", "defense", "special"}:
        try:
            moves = parse_move_lines(value, field)
        except ValueError as exc:
            await message.reply_text(f"<b>Invalid move list</b>\n\n{exc}", parse_mode="html")
            return
        move_sets = dict(hero.get("move_sets") or {})
        move_sets[field] = moves
        compatibility = {"move_sets": move_sets}
        _apply_move_compatibility(compatibility)
        updated = update_hero(hero["hero_key"], compatibility)
    else:
        updated = update_hero(hero["hero_key"], {field: value[:1000]})
    state.pop("field", None)
    await message.reply_text(
        f"<b>Character updated</b>\n\n{updated.get('name') if updated else hero.get('name')}\n"
        f"Changed → {field}\n\nChoose another field or return to the owner panel.",
        parse_mode="html",
        reply_markup=character_edit_markup(),
    )
    await log_event(client, "Character edited", f"{hero.get('name')} → {field}", message.from_user.id)


async def test_command(client, message):
    if not is_owner(message.from_user.id):
        return
    result = simulate_pve()
    if not result["ok"]:
        text = f"<b>PvE simulation unavailable</b>\n\n{result['reason']}"
    else:
        lines = "\n".join(f"{index + 1}. {line}" for index, line in enumerate(result["turns"]))
        text = (
            "<b>Owner test · PvE simulation</b>\n\n"
            f"Hero → <b>{result['hero']}</b>\n"
            f"Enemy → <b>{result['enemy']}</b>\n"
            f"Starting HP → {result['hero_hp']} / {result['enemy_hp']}\n\n"
            f"{lines}\n\n"
            f"Result → <b>{result['result']}</b>\n"
            "<i>No player data, rewards, or live battle records were changed.</i>"
        )
    await message.reply_text(text, parse_mode="html", reply_markup=owner_panel_markup())
    await log_event(client, "Owner test", "Deterministic PvE simulation executed", message.from_user.id)


async def admin_callback(client, callback_query):
    data = callback_query.data or ""
    if not data.startswith("admin:") or not is_owner(callback_query.from_user.id):
        return
    await callback_query.answer()
    action = data.split(":")
    if action[1] == "home":
        await callback_query.message.edit_text("<b>Owner control</b>\n\nChoose a tool →", parse_mode="html", reply_markup=owner_panel_markup())
    elif action[1] == "pending":
        items = list_submissions("pending")
        text = "<b>Approval queue</b>\n\n" + ("\n".join(f"· {item['title']}  →  {item['content_kind']}" for item in items[:12]) if items else "Nothing is waiting.")
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=pending_markup(items) if items else owner_panel_markup())
    elif action[1] == "mods":
        mods = list_moderators()
        text = "<b>Moderators</b>\n\n" + ("\n".join(f"· {mod.get('first_name') or 'Moderator'} · <code>{mod['telegram_id']}</code>\n  {', '.join(mod.get('permissions', [])) or 'no permissions'}" for mod in mods) if mods else "No moderators yet.")
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=owner_panel_markup())
    elif action[1] == "editfield":
        state = pending_character_edits.get(callback_query.from_user.id)
        if not state:
            await callback_query.message.edit_text(
                "<b>No character selected</b>\n\nUse /editchar CHARACTER_KEY first.",
                parse_mode="html",
                reply_markup=owner_panel_markup(),
            )
            return
        field = action[2]
        state["field"] = field
        if field in {"normal", "defense", "special"}:
            prompt = (
                f"Send the replacement {field} move list, one move per line:\n\n"
                "Name | Description | Damage | Unlock level | Cooldown | Effect"
            )
        else:
            prompt = f"Send the new {field.replace('_', ' ')}."
        await callback_query.message.reply_text(f"<b>Edit {field.replace('_', ' ')}</b>\n\n{prompt}", parse_mode="html")
    elif action[1] == "perm":
        target_id = int(action[2])
        permission = action[3]
        selected = pending_mod_permissions.setdefault(callback_query.from_user.id, set())
        if permission in selected:
            selected.remove(permission)
        else:
            selected.add(permission)
        await callback_query.message.edit_reply_markup(permission_markup(target_id, selected))
    elif action[1] == "save_mod":
        target_id = int(action[2])
        selected = sorted(pending_mod_permissions.get(callback_query.from_user.id, set()))
        first_name = pending_mod_names.get(callback_query.from_user.id, "Moderator")
        upsert_moderator(target_id, first_name, selected)
        await callback_query.message.edit_text(
            f"<b>Moderator saved</b>\n\nName → {first_name}\nID → <code>{target_id}</code>\nPermissions → {', '.join(selected) or 'none'}",
            parse_mode="html",
            reply_markup=owner_panel_markup(),
        )
        await log_event(client, "Admin added", f"Moderator {target_id} → {', '.join(selected) or 'no permissions'}", target_id)
    elif action[1] in {"approve", "reject"}:
        submission_id = action[2]
        item = next((item for item in list_submissions("pending") if str(item["_id"]) == submission_id), None)
        if action[1] == "approve" and item and item.get("content_kind") == "hero":
            payload = item.get("payload", {})
            if payload.get("rights_status") != "approved":
                await callback_query.message.edit_text(
                    "<b>Approval blocked</b>\n\nRights status must be approved before a hero can be published.",
                    parse_mode="html",
                    reply_markup=owner_panel_markup(),
                )
                return
            seed_hero({**payload, "status": "published"})
        elif action[1] == "approve" and item and item.get("content_kind") == "villain":
            payload = item.get("payload", {})
            if payload.get("rights_status") != "approved":
                await callback_query.message.edit_text(
                    "<b>Approval blocked</b>\n\nRights status must be approved before an enemy can be published.",
                    parse_mode="html",
                    reply_markup=owner_panel_markup(),
                )
                return
            publish_villain(payload)
        elif action[1] == "approve" and item and item.get("content_kind") == "event":
            publish_event(item.get("payload", {}))
        elif action[1] == "approve" and item:
            publish_content(item.get("content_kind", "content"), item.get("title", "Untitled"), item.get("payload", {}))
        review_submission(submission_id, "approved" if action[1] == "approve" else "rejected", str(callback_query.from_user.id))
        await callback_query.message.edit_text(f"<b>Submission {action[1]}d</b>\n\nReview recorded.", parse_mode="html", reply_markup=owner_panel_markup())
        if item:
            await log_event(
                client,
                "Owner approval" if action[1] == "approve" else "Owner rejection",
                f"{item.get('content_kind')} → {item.get('title')}",
                callback_query.from_user.id,
            )
    elif action[1] == "hero_guide":
        await callback_query.message.edit_text(
            "<b>Hero guide</b>\n\n"
            "Send /submithero to begin.\n"
            "The bot asks one question at a time and shows buttons for fixed choices.\n"
            "You will preview the hero and image before submitting it.\n"
            "Original or licensed only → owner approval before publish.",
            parse_mode="html",
            reply_markup=owner_panel_markup(),
        )
    elif action[1] == "enemy_guide":
        await callback_query.message.edit_text(
            "<b>Enemy guide</b>\n\n"
            "Send /submitvillain to begin the guided process.\n\n"
            "normal → repeatable PvE\nvillain → boss/Rift PvE\nevent_boss → event encounter",
            parse_mode="html",
            reply_markup=owner_panel_markup(),
        )
    elif action[1] == "event_guide":
        await callback_query.message.edit_text(
            "<b>Event guide</b>\n\n"
            "/submitevent key | Title | BossKey | Description | RewardCredits\n\n"
            "Publish the event boss first, then publish the event.",
            parse_mode="html",
            reply_markup=owner_panel_markup(),
        )
    elif action[1] == "kind_guide":
        await callback_query.message.edit_text("<b>Content kinds</b>\n\nuniverse → faction → enemy → boss → relic → mission → banner → event → currency\n\nSubmit with /submitkind KIND TITLE | DEFINITION.", parse_mode="html", reply_markup=owner_panel_markup())
    elif action[1] == "art_guide":
        await callback_query.message.edit_text(
            "<b>AI artwork rights</b>\n\n"
            "Original hero → new name, new costume, new symbol, new silhouette, new story.\n"
            "Avoid protected franchise names, logos, actor likenesses, and exact costume prompts.\n"
            "AI generation does not grant commercial rights.\n"
            "Licensed artwork → keep written permission and mark the hero licensed before publishing.",
            parse_mode="html",
            reply_markup=owner_panel_markup(),
        )


def register(client) -> None:
    client.add_handler(MessageHandler(owner_command, filters.command("owner")))
    client.add_handler(MessageHandler(addmod_command, filters.command("addmod")))
    client.add_handler(MessageHandler(submitevent_command, filters.command("submitevent")))
    client.add_handler(MessageHandler(submitkind_command, filters.command("submitkind")))
    client.add_handler(MessageHandler(adminhelp_command, filters.command("adminhelp")))
    client.add_handler(MessageHandler(guideadmin_command, filters.command("guideadmin")))
    client.add_handler(MessageHandler(pending_command, filters.command("pending")))
    client.add_handler(MessageHandler(test_command, filters.command("test")))
    client.add_handler(MessageHandler(editchar_command, filters.command(["editchar", "edit_char"])))
    client.add_handler(MessageHandler(playersearch_command, filters.command("playersearch")))
    client.add_handler(CallbackQueryHandler(admin_callback, filters.regex(r"^admin:")))
    register_content_wizard(client)
    client.add_handler(MessageHandler(character_edit_text, filters.private & filters.text), group=2)