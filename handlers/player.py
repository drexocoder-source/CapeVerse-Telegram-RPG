from pathlib import Path

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.mongo import (
    add_hero_to_player,
    get_or_create_user,
    get_profile,
    get_team,
    list_owned_heroes,
    save_team,
    update_player,
)
from guide import ensure_guide_pdf
from plugins.arena import start_arena
from plugins.battle import resolve_action, start_battle
from plugins.missions import claim_patrol
from plugins.recruitment import pull
from plugins.rift import start_rift
from utils.formatting import back_markup, main_menu_markup, origin_markup, profile_text, rarity_mark
from utils.profile_card import generate_profile_card


ORIGINS = {
    "enhanced": ("Enhanced", "Second Wind", "ironbark_sentinel"),
    "tech": ("Tech", "Rapid Calibration", "volt_warden"),
    "mystic": ("Mystic", "Ember Memory", "ash_oracle"),
}


def _player(message):
    return get_or_create_user(
        message.from_user.id,
        getattr(message.from_user, "username", "") or "",
        getattr(message.from_user, "first_name", "") or "",
    )


async def send_guide(message) -> None:
    path = ensure_guide_pdf()
    await message.reply_document(
        document=str(path),
        caption="<b>CapeVerse Player Guide</b>\n\nRead this before your first signal.\nUse /guide whenever you need it again.",
        parse_mode="html",
    )


def _battle_markup(battle_id: str, finished: bool = False) -> InlineKeyboardMarkup:
    if finished:
        return InlineKeyboardMarkup([[InlineKeyboardButton("← Main menu", callback_data="menu:home")]])
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Signature →", callback_data=f"battle:{battle_id}:signature"),
                InlineKeyboardButton("Utility →", callback_data=f"battle:{battle_id}:utility"),
            ],
            [InlineKeyboardButton("Ultimate →", callback_data=f"battle:{battle_id}:ultimate")],
            [InlineKeyboardButton("← Main menu", callback_data="menu:home")],
        ]
    )


def _battle_text(battle: dict, enemy_name: str) -> str:
    latest = battle.get("log", [])[-1:] if battle else []
    log_line = f"\n\n<i>{latest[0]}</i>" if latest else ""
    return (
        f"<b>{battle.get('stage', 'Battle')}</b>\n"
        f"{enemy_name}  →  HP {battle.get('enemy_hp', 0)}\n"
        f"Your team →  HP {battle.get('player_hp', 0)}\n"
        f"Turn {battle.get('turn', 1)}  →  choose an action{log_line}"
    )


async def show_profile(message, edit: bool = False) -> None:
    profile = get_profile(message.from_user.id) or {}
    heroes = list_owned_heroes(message.from_user.id)
    team = get_team(message.from_user.id)
    synergy = min(15, max(0, len({hero.get("universe") for hero in team}) - 1) * 5)
    text = profile_text(profile, len(heroes), len(team), synergy)
    if edit:
        await message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    card = generate_profile_card(profile, heroes, len(team), synergy)
    await message.reply_photo(
        photo=str(card),
        caption=text,
        parse_mode="html",
        reply_markup=back_markup(),
    )


async def start_command(client, message):
    profile = _player(message)
    if profile.get("origin"):
        await message.reply_text(
            "<b>CapeVerse</b>\n\nYour signal is active.\nChoose your next move →",
            parse_mode="html",
            reply_markup=main_menu_markup(),
        )
        return
    await message.reply_text(
        "<b>CapeVerse</b>\n\nYour signal has been detected.\n\nChoose an Origin →\n<i>Your choice grants one starter hero and one permanent passive.</i>",
        parse_mode="html",
        reply_markup=origin_markup(),
    )
    if not profile.get("guide_sent"):
        await send_guide(message)
        update_player(message.from_user.id, guide_sent=True)


async def guide_command(client, message):
    _player(message)
    await send_guide(message)


async def menu_command(client, message):
    _player(message)
    await message.reply_text(
        "<b>CapeVerse</b>\n\nChoose your next move →",
        parse_mode="html",
        reply_markup=main_menu_markup(),
    )


async def profile_command(client, message):
    _player(message)
    await show_profile(message)


async def callback_handler(client, callback_query):
    data = callback_query.data or ""
    user_id = callback_query.from_user.id
    await callback_query.answer()

    if data.startswith("origin:"):
        key = data.split(":", 1)[1]
        origin = ORIGINS.get(key)
        if not origin:
            return
        label, passive, starter_key = origin
        profile = get_profile(user_id) or {}
        if not profile.get("origin"):
            update_player(user_id, origin=label, passive=passive)
            owned = add_hero_to_player(user_id, starter_key)
            if owned:
                save_team(user_id, [str(owned["_id"])])
        hero = next((hero for hero in list_owned_heroes(user_id) if hero["hero_key"] == starter_key), None)
        await callback_query.message.edit_text(
            f"<b>Origin locked → {label}</b>\n\n"
            f"Passive → <b>{passive}</b>\n"
            f"Starter → {hero.get('name', 'Your first hero') if hero else 'Starter hero'}\n\n"
            "Team 1 is ready.\nYour first threat is waiting →",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Begin first battle →", callback_data="menu:battle")], [InlineKeyboardButton("Main menu", callback_data="menu:home")]]
            ),
        )
        return

    if data == "menu:home":
        await callback_query.message.edit_text(
            "<b>CapeVerse</b>\n\nChoose your next move →",
            parse_mode="html",
            reply_markup=main_menu_markup(),
        )
        return
    if data == "menu:profile":
        await show_profile(callback_query.message, edit=True)
        return
    if data == "menu:guide":
        await send_guide(callback_query.message)
        return
    if data == "menu:heroes":
        heroes = list_owned_heroes(user_id)
        if not heroes:
            text = "<b>Hero Codex</b>\n\nNo heroes collected yet.\nRecruitment opens your first signal →"
        else:
            rows = "\n".join(
                f"{rarity_mark(hero.get('rarity', 'Common'))} <b>{hero['name']}</b>  ·  Lv {hero.get('level', 1)}  ·  ★ {hero.get('stars', 1)}\n"
                f"   {hero['role']}  →  {hero['universe']}"
                for hero in heroes
            )
            text = f"<b>Hero Codex</b>\n\n{rows}"
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    if data == "menu:team":
        team = get_team(user_id)
        if not team:
            text = "<b>Team 1</b>\n\nYour team is empty.\nChoose an Origin first →"
        else:
            members = "\n".join(f"{hero['slot'] if 'slot' in hero else index + 1}  →  <b>{hero['name']}</b>  ·  {hero['role']}" for index, hero in enumerate(team))
            text = f"<b>Team 1</b>\n\n{members}\n\nThree slots → roles → synergy"
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    if data == "menu:recruit":
        profile = get_profile(user_id) or {}
        await callback_query.message.edit_text(
            "<b>Recruitment Beacon</b>\n\n"
            f"Signal Shards → <b>{profile.get('signal_shards', 0)}</b>\n"
            "One pull → 1 Signal Shard\n"
            "Signal Boost → visible in the Beacon log\n\n"
            "Choose your pull →",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Pull 1 signal →", callback_data="recruit:pull")], [InlineKeyboardButton("← Back", callback_data="menu:home")]]
            ),
        )
        return
    if data == "recruit:pull":
        result = pull(user_id)
        if not result["ok"]:
            text = f"<b>Beacon paused</b>\n\n{result['reason']}"
        else:
            hero = result["hero"]
            text = (
                "<b>Signal received</b>\n\n"
                f"{rarity_mark(hero.get('rarity', 'Common'))} <b>{hero['name']}</b>\n"
                f"{hero['role']}  →  {hero['universe']}\n\n"
                f"{hero['description']}\n\n"
                f"Signal Shards remaining → {result['balance']}"
            )
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    if data == "menu:missions":
        profile = get_profile(user_id) or {}
        await callback_query.message.edit_text(
            "<b>Missions</b>\n\n"
            "Patrol → claim a quick city reward\n"
            "Case Files → follow branching story paths\n\n"
            f"Patrol Intel → <b>{profile.get('patrol_intel', 0)}</b>",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Claim Patrol →", callback_data="mission:patrol")], [InlineKeyboardButton("Case File 01 →", callback_data="menu:battle")], [InlineKeyboardButton("← Back", callback_data="menu:home")]]
            ),
        )
        return
    if data == "mission:patrol":
        result = claim_patrol(user_id)
        text = f"<b>Patrol complete</b>\n\n+ {result.get('credits', 0)} Cape Credits\n→ The city keeps moving." if result["ok"] else f"<b>Patrol unavailable</b>\n\n{result['reason']}"
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    if data == "menu:battle":
        battle_info = start_battle(user_id, "tutorial", "Case File 01 · Broken Signal")
        battle = {"stage": "Case File 01 · Broken Signal", "enemy_hp": battle_info["enemy_hp"], "player_hp": 100, "turn": 1}
        await callback_query.message.edit_text(_battle_text(battle, battle_info["enemy_name"]), parse_mode="html", reply_markup=_battle_markup(battle_info["id"]))
        return
    if data == "menu:arena":
        battle_info = start_arena(user_id)
        battle = {"stage": "Sanctioned Bout", "enemy_hp": battle_info["enemy_hp"], "player_hp": 100, "turn": 1}
        await callback_query.message.edit_text(_battle_text(battle, battle_info["enemy_name"]), parse_mode="html", reply_markup=_battle_markup(battle_info["id"]))
        return
    if data == "menu:rift":
        profile = get_profile(user_id) or {}
        floor = int(profile.get("rift_floor", 1))
        battle_info = start_rift(user_id, floor)
        battle = {"stage": f"The Rift · Floor {floor}", "enemy_hp": battle_info["enemy_hp"], "player_hp": 100, "turn": 1}
        await callback_query.message.edit_text(_battle_text(battle, battle_info["enemy_name"]), parse_mode="html", reply_markup=_battle_markup(battle_info["id"]))
        return
    if data.startswith("battle:"):
        _, battle_id, action = data.split(":", 2)
        battle = resolve_action(user_id, battle_id, action)
        if not battle:
            await callback_query.message.edit_text("<b>Battle expired</b>\n\nReturn to the menu and start a new encounter →", parse_mode="html", reply_markup=back_markup())
            return
        enemy_name = "The Null Regent" if battle["mode"] == "rift" else "Rival Captain" if battle["mode"] == "arena" else "Null Hound"
        finished = battle["status"] != "active"
        result_line = "\n\n<b>Victory → reward pending</b>" if battle["status"] == "won" else "\n\n<b>Defeat → regroup and try again</b>" if battle["status"] == "lost" else ""
        await callback_query.message.edit_text(_battle_text(battle, enemy_name) + result_line, parse_mode="html", reply_markup=_battle_markup(battle_id, finished))


def register(client) -> None:
    client.add_handler(__import__("pyrogram").handlers.MessageHandler(start_command, filters.command("start")))
    client.add_handler(__import__("pyrogram").handlers.MessageHandler(guide_command, filters.command("guide")))
    client.add_handler(__import__("pyrogram").handlers.MessageHandler(menu_command, filters.command(["menu", "help"])))
    client.add_handler(__import__("pyrogram").handlers.MessageHandler(profile_command, filters.command("profile")))
    client.add_handler(__import__("pyrogram").handlers.CallbackQueryHandler(callback_handler))