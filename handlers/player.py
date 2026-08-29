from pathlib import Path

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.mongo import (
    add_hero_to_player,
    get_or_create_user,
    get_or_create_user_with_status,
    get_profile,
    get_starter_hero,
    get_team,
    list_owned_heroes,
    list_relics,
    save_team,
    update_player,
)
from guide import ensure_guide_pdf
from plugins.arena import start_arena
from plugins.battle import resolve_action, start_battle
from plugins.missions import claim_patrol, complete_case
from plugins.relics import craft_relic
from plugins.recruitment import pull
from plugins.rift import start_rift
from plugins.events import available_events, start_event_boss
from utils.formatting import back_markup, main_menu_markup, origin_markup, profile_text, rarity_mark
from utils.profile_card import generate_profile_card
from utils.audit import log_event


ORIGINS = {
    "enhanced": ("Enhanced", "Second Wind"),
    "tech": ("Tech", "Rapid Calibration"),
    "mystic": ("Mystic", "Ember Memory"),
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


def _battle_markup(
    battle_id: str,
    finished: bool = False,
    mode: str = "",
    move_names: dict | None = None,
    nemesis_available: bool = False,
) -> InlineKeyboardMarkup:
    if finished:
        return InlineKeyboardMarkup([[InlineKeyboardButton("← Main menu", callback_data="menu:home")]])
    names = move_names or {}
    rows = [
            [
                InlineKeyboardButton(f"{names.get('signature', 'Signature')[:22]} →", callback_data=f"battle:{battle_id}:signature"),
                InlineKeyboardButton(f"{names.get('utility', 'Utility')[:22]} →", callback_data=f"battle:{battle_id}:utility"),
            ],
            [InlineKeyboardButton(f"{names.get('ultimate', 'Ultimate')[:28]} →", callback_data=f"battle:{battle_id}:ultimate")],
    ]
    if nemesis_available:
        rows.append([InlineKeyboardButton(f"{names.get('nemesis', 'Nemesis Ultimate')[:28]} →", callback_data=f"battle:{battle_id}:nemesis")])
    rows.append([InlineKeyboardButton("← Main menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def _battle_text(battle: dict, enemy_name: str | None = None) -> str:
    latest = battle.get("log", [])[-1:] if battle else []
    log_line = f"\n\n<i>{latest[0]}</i>" if latest else ""
    return (
        f"<b>{battle.get('stage', 'Battle')}</b>\n"
        f"{enemy_name or battle.get('enemy_name', 'Threat')}  →  HP {battle.get('enemy_hp', 0)}\n"
        f"{battle.get('actor_name', 'Your hero')} →  HP {battle.get('player_hp', 0)}\n"
        f"Turn {battle.get('turn', 1)}  →  choose an action{log_line}"
    )


async def show_profile(message, edit: bool = False, telegram_id: int | None = None) -> None:
    player_id = telegram_id or message.from_user.id
    profile = get_profile(player_id) or {}
    heroes = list_owned_heroes(player_id)
    team = get_team(player_id)
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
    profile, created = get_or_create_user_with_status(
        message.from_user.id,
        getattr(message.from_user, "username", "") or "",
        getattr(message.from_user, "first_name", "") or "",
    )
    if created:
        await log_event(client, "New user", "Player started CapeVerse", message.from_user.id)
    if profile.get("origin"):
        if not list_owned_heroes(message.from_user.id):
            starter = get_starter_hero(profile["origin"])
            if starter:
                owned = add_hero_to_player(message.from_user.id, starter["hero_key"])
                if owned:
                    save_team(message.from_user.id, [str(owned["_id"])])
                    await log_event(client, "New character", f"{starter['name']} granted as {profile['origin']} starter", message.from_user.id)
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
    if data.startswith("admin:"):
        return
    user_id = callback_query.from_user.id
    await callback_query.answer()

    if data.startswith("origin:"):
        key = data.split(":", 1)[1]
        origin = ORIGINS.get(key)
        if not origin:
            return
        label, passive = origin
        profile = get_profile(user_id) or {}
        if not profile.get("origin"):
            update_player(user_id, origin=label, passive=passive)
            starter = get_starter_hero(label)
            if starter:
                owned = add_hero_to_player(user_id, starter["hero_key"])
                if owned:
                    save_team(user_id, [str(owned["_id"])])
                    await log_event(client, "New character", f"{starter['name']} granted as {label} starter", user_id)
        hero = get_starter_hero(label)
        if not hero:
            await callback_query.message.edit_text(
                f"<b>Origin saved → {label}</b>\n\n"
                f"Passive → <b>{passive}</b>\n\n"
                "No starter hero is published for this Origin yet.\n"
                "The owner must add one with /submithero → StarterOrigin.",
                parse_mode="html",
                reply_markup=back_markup(),
            )
            return
        await callback_query.message.edit_text(
            f"<b>Origin locked → {label}</b>\n\n"
            f"Passive → <b>{passive}</b>\n"
            f"Starter → {hero['name']}\n\n"
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
        await show_profile(callback_query.message, edit=True, telegram_id=user_id)
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
    if data == "menu:relics":
        relics = list_relics(user_id)
        rows = "\n".join(
            f"◆ <b>{relic['name']}</b>  ·  {relic['slot']}\n"
            f"   {relic['base_stat']}  →  {relic['substat']}"
            for relic in relics[:10]
        ) or "No relics owned yet."
        await callback_query.message.edit_text(
            f"<b>Relics</b>\n\n{rows}\n\nForge cost → 100 Cape Credits",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Forge one relic →", callback_data="relic:craft")], [InlineKeyboardButton("← Back", callback_data="menu:home")]]
            ),
        )
        return
    if data == "relic:craft":
        result = craft_relic(user_id)
        if result["ok"]:
            relic = result["relic"]
            text = f"<b>Relic forged</b>\n\n◆ {relic['name']}\n{relic['slot']}  →  {relic['base_stat']}\nSubstat → {relic['substat']}\n\nCape Credits → {result['balance']}"
        else:
            text = f"<b>Forge unavailable</b>\n\n{result['reason']}"
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    if data == "menu:recruit":
        profile = get_profile(user_id) or {}
        await callback_query.message.edit_text(
            "<b>Recruitment Beacon</b>\n\n"
            f"Signal Shards → <b>{profile.get('signal_shards', 0)}</b>\n"
            "One pull → 1 Signal Shard\n"
            f"Signal Boost → <b>{profile.get('signal_boost', 0)}%</b>\n\n"
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
                f"Signal Shards remaining → {result['balance']}\n"
                f"Signal Boost → {result['signal_boost']}%"
            )
            await log_event(client, "New character", f"Beacon collected → {hero['name']}", user_id)
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
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Claim Patrol →", callback_data="mission:patrol")],
                [InlineKeyboardButton("Protect civilians →", callback_data="mission:case:Hero")],
                [InlineKeyboardButton("Pursue the threat →", callback_data="mission:case:Vigilante")],
                [InlineKeyboardButton("← Back", callback_data="menu:home")],
            ]),
        )
        return
    if data == "mission:patrol":
        result = claim_patrol(user_id)
        text = f"<b>Patrol complete</b>\n\n+ {result.get('credits', 0)} Cape Credits\n→ The city keeps moving." if result["ok"] else f"<b>Patrol unavailable</b>\n\n{result['reason']}"
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    if data.startswith("mission:case:"):
        alignment = data.split(":", 2)[2]
        result = complete_case(user_id, alignment)
        text = (
            f"<b>Case File resolved</b>\n\nChoice → {result['alignment']}\nReward → +{result['credits']} Cape Credits\nAlignment updated →"
            if result["ok"]
            else f"<b>Case File unavailable</b>\n\n{result['reason']}"
        )
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    if data == "menu:battle":
        await callback_query.message.edit_text(
            "<b>PvE operations</b>\n\n"
            "Normal enemy → repeatable street encounter\n"
            "Villain hunt → stronger published villain\n\n"
            "Choose the threat →",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Fight normal enemy →", callback_data="pve:normal")],
                [InlineKeyboardButton("Hunt a villain →", callback_data="pve:villain")],
                [InlineKeyboardButton("← Back", callback_data="menu:home")],
            ]),
        )
        return
    if data in {"pve:normal", "pve:villain"}:
        mode = "story" if data == "pve:normal" else "villain"
        stage = "Street Operation" if mode == "story" else "Villain Hunt"
        battle_info = start_battle(user_id, mode, stage)
        if not battle_info["ok"]:
            await callback_query.message.edit_text(f"<b>PvE unavailable</b>\n\n{battle_info['reason']}", parse_mode="html", reply_markup=back_markup())
            return
        battle = {
            "stage": stage,
            "enemy_hp": battle_info["enemy_hp"],
            "player_hp": 100,
            "turn": 1,
            "actor_name": battle_info["actor_name"],
        }
        await callback_query.message.edit_text(
            _battle_text(battle, battle_info["enemy_name"]),
            parse_mode="html",
            reply_markup=_battle_markup(
                battle_info["id"],
                mode=mode,
                move_names=battle_info["move_names"],
                nemesis_available=battle_info["nemesis_available"],
            ),
        )
        return
    if data == "menu:arena":
        battle_info = start_arena(user_id)
        if not battle_info["ok"]:
            await callback_query.message.edit_text(f"<b>Arena unavailable</b>\n\n{battle_info['reason']}", parse_mode="html", reply_markup=back_markup())
            return
        battle = {"stage": "Sanctioned Bout", "enemy_hp": battle_info["enemy_hp"], "player_hp": 100, "turn": 1}
        battle["actor_name"] = battle_info["actor_name"]
        await callback_query.message.edit_text(_battle_text(battle, battle_info["enemy_name"]), parse_mode="html", reply_markup=_battle_markup(battle_info["id"], mode="arena", move_names=battle_info["move_names"]))
        return
    if data == "menu:rift":
        profile = get_profile(user_id) or {}
        floor = int(profile.get("rift_floor", 1))
        battle_info = start_rift(user_id, floor)
        if not battle_info["ok"]:
            await callback_query.message.edit_text(f"<b>The Rift is unavailable</b>\n\n{battle_info['reason']}", parse_mode="html", reply_markup=back_markup())
            return
        battle = {"stage": f"The Rift · Floor {floor}", "enemy_hp": battle_info["enemy_hp"], "player_hp": 100, "turn": 1}
        battle["actor_name"] = battle_info["actor_name"]
        await callback_query.message.edit_text(_battle_text(battle, battle_info["enemy_name"]), parse_mode="html", reply_markup=_battle_markup(battle_info["id"], mode="rift", move_names=battle_info["move_names"], nemesis_available=battle_info["nemesis_available"]))
        return
    if data == "menu:events":
        events = available_events()
        if not events:
            await callback_query.message.edit_text(
                "<b>Events</b>\n\nNo event with a published boss is active yet.",
                parse_mode="html",
                reply_markup=back_markup(),
            )
            return
        rows = [[InlineKeyboardButton(f"{event['title'][:28]} →", callback_data=f"event:start:{event['event_key']}")] for event in events[:10]]
        rows.append([InlineKeyboardButton("← Back", callback_data="menu:home")])
        text = "<b>Active events</b>\n\n" + "\n".join(f"· {event['title']}\n  {event['description']}" for event in events[:10])
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=InlineKeyboardMarkup(rows))
        return
    if data.startswith("event:start:"):
        event_key = data.split(":", 2)[2]
        battle_info = start_event_boss(user_id, event_key)
        if not battle_info["ok"]:
            await callback_query.message.edit_text(f"<b>Event unavailable</b>\n\n{battle_info['reason']}", parse_mode="html", reply_markup=back_markup())
            return
        battle = {
            "stage": "Event Boss",
            "enemy_hp": battle_info["enemy_hp"],
            "player_hp": 100,
            "turn": 1,
            "actor_name": battle_info["actor_name"],
        }
        await callback_query.message.edit_text(
            _battle_text(battle, battle_info["enemy_name"]),
            parse_mode="html",
            reply_markup=_battle_markup(
                battle_info["id"],
                mode="event",
                move_names=battle_info["move_names"],
                nemesis_available=battle_info["nemesis_available"],
            ),
        )
        return
    if data.startswith("battle:"):
        _, battle_id, action = data.split(":", 2)
        battle = resolve_action(user_id, battle_id, action)
        if not battle:
            await callback_query.message.edit_text("<b>Battle expired</b>\n\nReturn to the menu and start a new encounter →", parse_mode="html", reply_markup=back_markup())
            return
        finished = battle["status"] != "active"
        result_line = "\n\n<b>Victory → reward pending</b>" if battle["status"] == "won" else "\n\n<b>Defeat → regroup and try again</b>" if battle["status"] == "lost" else ""
        await callback_query.message.edit_text(
            _battle_text(battle) + result_line,
            parse_mode="html",
            reply_markup=_battle_markup(
                battle_id,
                finished,
                battle["mode"],
                battle.get("move_names", {}),
                bool(battle.get("nemesis_available")),
            ),
        )
        if finished:
            await log_event(client, "Battle result", f"{battle['mode']} → {battle['status']} against {battle.get('enemy_name', 'threat')}", user_id)


def register(client) -> None:
    client.add_handler(MessageHandler(start_command, filters.command("start")))
    client.add_handler(MessageHandler(guide_command, filters.command("guide")))
    client.add_handler(MessageHandler(menu_command, filters.command(["menu", "help"])))
    client.add_handler(MessageHandler(profile_command, filters.command("profile")))
    client.add_handler(CallbackQueryHandler(callback_handler))