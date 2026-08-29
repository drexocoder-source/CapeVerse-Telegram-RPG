import json
import os
from typing import Any

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.mongo import (
    add_submission,
    get_hero,
    list_moderators,
    list_submissions,
    review_submission,
    seed_hero,
    upsert_moderator,
)


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
                InlineKeyboardButton("Add hero guide", callback_data="admin:hero_guide"),
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


def _target_from_message(message) -> int | None:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    parts = (message.text or "").split()
    if len(parts) > 1 and parts[1].isdigit():
        return int(parts[1])
    return None


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
    await message.reply_text(
        f"<b>Moderator access</b>\n\nUser → <code>{target_id}</code>\n"
        "Tap permissions to grant or remove them.\n"
        "Save when finished →",
        parse_mode="html",
        reply_markup=permission_markup(target_id, set()),
    )


async def submithero_command(client, message):
    user_id = message.from_user.id
    if not can(user_id, "submit_heroes"):
        return
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2:
        await message.reply_text(
            "<b>Hero submission format</b>\n\n"
            "/submithero key | Name | Codename | Source | Universe | Faction | Role | Rarity | Alignment | Description | Signature | Utility | Ultimate | RightsStatus\n\n"
            "Use RightsStatus = approved only when you have rights or the hero is original.\n"
            "The owner must approve every submission before publishing.",
            parse_mode="html",
        )
        return
    fields = [field.strip() for field in raw[1].split("|")]
    if len(fields) != 14:
        await message.reply_text("<b>Submission not saved</b>\n\nUse exactly 14 fields separated by |.\nSend /submithero to see the guide again.", parse_mode="html")
        return
    keys = ["hero_key", "name", "codename", "source", "universe", "faction", "role", "rarity", "alignment", "description", "ability_signature", "ability_utility", "ability_ultimate", "rights_status"]
    payload = dict(zip(keys, fields))
    payload["hero_key"] = payload["hero_key"].lower().replace(" ", "_")
    payload["status"] = "draft"
    submission_id = add_submission("hero", payload["name"], payload, str(user_id))
    await message.reply_text(
        f"<b>Hero submitted → pending</b>\n\n{payload['name']}\nSubmission ID → <code>{submission_id}</code>\n\nThe owner must approve it from /owner.",
        parse_mode="html",
    )


async def submitkind_command(client, message):
    user_id = message.from_user.id
    if not can(user_id, "submit_content"):
        return
    raw = (message.text or "").split(maxsplit=2)
    if len(raw) < 3:
        await message.reply_text(
            "<b>New content kind</b>\n\n"
            "/submitkind KIND | TITLE | DEFINITION\n\n"
            "Examples → universe, faction, enemy, boss, relic, mission, banner, event, currency",
            parse_mode="html",
        )
        return
    parts = [part.strip() for part in raw[1].split("|", 1)]
    title_and_definition = raw[2].split("|", 1)
    title = parts[0]
    definition = title_and_definition[-1].strip() if title_and_definition else ""
    add_submission(parts[0], title, {"details": definition}, str(user_id))
    await message.reply_text(f"<b>Content queued → {parts[0]}</b>\n\n{title}\nOwner review is required.", parse_mode="html")


async def adminhelp_command(client, message):
    if not (is_owner(message.from_user.id) or moderator_permissions(message.from_user.id)):
        return
    await message.reply_text(
        "<b>Admin guide</b>\n\n"
        "<b>Owner</b>\n"
        "/owner → open control panel\n"
        "Reply to a user + /addmod → grant exact permissions\n"
        "/pending → review queue\n"
        "/submithero → submit a hero\n"
        "/submitkind → submit a new content kind\n\n"
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
        text = "<b>Moderators</b>\n\n" + ("\n".join(f"· {mod.get('username') or mod['telegram_id']}  →  {', '.join(mod.get('permissions', [])) or 'no permissions'}" for mod in mods) if mods else "No moderators yet.")
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=owner_panel_markup())
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
        upsert_moderator(target_id, "", selected)
        await callback_query.message.edit_text(
            f"<b>Moderator saved</b>\n\nUser → <code>{target_id}</code>\nPermissions → {', '.join(selected) or 'none'}",
            parse_mode="html",
            reply_markup=owner_panel_markup(),
        )
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
        review_submission(submission_id, "approved" if action[1] == "approve" else "rejected", str(callback_query.from_user.id))
        await callback_query.message.edit_text(f"<b>Submission {action[1]}d</b>\n\nReview recorded.", parse_mode="html", reply_markup=owner_panel_markup())
    elif action[1] == "hero_guide":
        await callback_query.message.edit_text(
            "<b>Hero guide</b>\n\n"
            "Submit with /submithero and 14 pipe-separated fields.\n"
            "Required → key, name, codename, source, universe, faction, role, rarity, alignment, description, three abilities, rights status.\n"
            "Original or licensed only → owner approval before publish.",
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
    client.add_handler(MessageHandler(submithero_command, filters.command("submithero")))
    client.add_handler(MessageHandler(submitkind_command, filters.command("submitkind")))
    client.add_handler(MessageHandler(adminhelp_command, filters.command("adminhelp")))
    client.add_handler(MessageHandler(guideadmin_command, filters.command("guideadmin")))
    client.add_handler(MessageHandler(pending_command, filters.command("pending")))
    client.add_handler(CallbackQueryHandler(admin_callback))