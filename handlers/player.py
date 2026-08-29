from html import escape
from pathlib import Path

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.mongo import (
    add_hero_to_player,
    claim_timed_reward,
    evolve_character,
    get_hero,
    get_or_create_user,
    get_owned_hero,
    get_or_create_user_with_status,
    get_profile,
    get_starter_hero,
    get_team,
    inventory_summary,
    is_character_researched,
    list_heroes,
    list_owned_heroes,
    list_relics,
    research_character,
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
from utils.profile_card import generate_character_card, generate_profile_card
from utils.audit import log_event


ORIGINS = {
    "enhanced": ("Enhanced", "Second Wind"),
    "tech": ("Tech", "Rapid Calibration"),
    "mystic": ("Mystic", "Ember Memory"),
}

GUIDE_TOPICS = {
    "start": (
        "Getting started",
        "<b>Getting started</b>\n\n"
        "/start creates your player record.\n"
        "Choose Enhanced, Tech, or Mystic → receive that Origin’s published starter hero.\n"
        "Your Telegram first name is shown; your numeric Telegram ID keeps the account unique.",
    ),
    "currency": (
        "Currencies",
        "<b>Currencies</b>\n\n"
        "Cape Credits → relic forging and progression\n"
        "Signal Shards → Recruitment Beacon pulls\n"
        "Prism Cores → premium-event currency reserved for future systems\n"
        "Patrol Intel → Case Files and mission choices\n"
        "Signal Boost → increases until a high-rarity Beacon result is guaranteed\n\n"
        "<b>How to earn</b>\n"
        "New account → 500 Cape Credits, 2 Signal Shards, 5 Patrol Intel\n"
        "Patrol → spend 1 Patrol Intel, earn +120 Cape Credits\n"
        "Case File → spend 1 Patrol Intel, earn +90 Hero or +110 Vigilante/Antihero Credits\n"
        "Normal battle → +75 Cape Credits on victory\n"
        "Arena victory → +100 Cape Credits and +10 rating\n"
        "Rift victory → +150 Cape Credits and advance one floor\n"
        "Event boss → the reward configured for that event\n\n"
        "Recruitment costs 1 Signal Shard. Relic forging costs 100 Cape Credits."
    ),
    "commands": (
        "Commands",
        "<b>Player commands</b>\n\n"
        "/start → create or reopen your account\n"
        "/main or /menu → open the main game menu\n"
        "/profile → generate your profile card\n"
        "/inventory → wallet, collection, relics, and reward access\n"
        "/char NAME → global codex story, photo, moves, and research/evolution\n"
        "/mychar NAME → your owned character, XP, stars, and actions\n"
        "/daily and /weekly → timed signal rewards\n"
        "/guide → open this guide center\n"
        "/help → open the main menu",
    ),
    "heroes": (
        "Heroes and teams",
        "<b>Heroes and teams</b>\n\n"
        "Heroes may be Human, Enhanced Human, Tech-Enhanced, Mystic, Alien, or another custom type.\n"
        "They are grouped by universe, place, faction, role, rarity, and alignment.\n"
        "A team holds up to three owned heroes. Duplicate pulls increase stars.\n"
        "Use /char to see the designer card, character XP, moves, unlock levels, cooldowns, effects, and evolution.",
    ),
    "recruit": (
        "Catching heroes",
        "<b>Recruitment and collecting</b>\n\n"
        "Open Recruitment Beacon from /main.\n"
        "One pull costs 1 Signal Shard and gives one published hero.\n"
        "A new hero joins your collection. A duplicate increases that hero’s stars.\n\n"
        "Signal Boost rises by 10 after ordinary pulls. At 90, the next pull uses the Epic/Legendary/Mythic pool and the meter resets.\n"
        "New players begin with 2 Signal Shards. More Shard reward sources can be added through future events and missions.",
    ),
    "progression": (
        "Evolution and research",
        "<b>Player and character progression</b>\n\n"
        "Player XP → Patrol +15 · Case File +20 · battle victories +30 to +50\n"
        "Character XP → the active hero earns battle XP\n"
        "XP needed for the next level → current level × 100\n\n"
        "Moves unlock at their configured character levels. Locked moves appear in /char but not in battle.\n"
        "Original CapeVerse characters may evolve at character level 10 with 3 stars.\n"
        "Licensed suit generations and documented forms use Research Archives instead of evolution.\n"
        "Use /mychar for owned progression and /char for global research information.",
    ),
    "inventory": (
        "Inventory and rewards",
        "<b>Inventory · Version 0.8</b>\n\n"
        "Registration begins with 500 Cape Credits, 2 Signal Shards, 5 Patrol Intel, and 0 Prism Cores.\n"
        "/inventory shows currencies, owned characters, relics, and research archives.\n\n"
        "/daily gives a small credit, Intel, and XP reward.\n"
        "/weekly gives Credits, Intel, XP, and one Signal Shard.\n"
        "Claim timers and streaks are stored in MongoDB, so restarting the bot cannot reset them.",
    ),
    "combat": (
        "Combat",
        "<b>Combat</b>\n\n"
        "Signature → reliable character damage\n"
        "Normal moves → standard attacks\n"
        "Defense moves → reduce the incoming counterattack\n"
        "Special moves → stronger attacks with higher levels or cooldowns\n"
        "Nemesis Ultimate → appears only against a linked villain\n\n"
        "Only moves unlocked at the active character’s level appear. Used moves may enter cooldown.",
    ),
    "pve": (
        "PvE and Rift",
        "<b>PvE and Rift</b>\n\n"
        "Normal enemies → repeatable street operations\n"
        "Villains → stronger hunts and Rift encounters\n"
        "Rift victories increase your floor. Battles award Cape Credits when completed.",
    ),
    "events": (
        "Events",
        "<b>Events</b>\n\n"
        "The owner publishes an event boss first, then links that boss to an event.\n"
        "Players receive a limited boss encounter and the event’s configured Cape Credit reward.",
    ),
    "relics": (
        "Relics",
        "<b>Relics</b>\n\n"
        "Spend 100 Cape Credits to forge one relic.\n"
        "Relics have a slot, set, rarity, base stat, and substat.\n"
        "They remain in your permanent inventory.",
    ),
    "admin": (
        "Owner and admin",
        "<b>Owner and admin guide</b>\n\n"
        "/owner → owner tools\n"
        "/submithero → guided hero creation\n"
        "/submitvillain → guided enemy creation\n"
        "/submitevent → event submission\n"
        "/pending → approval queue\n"
        "/test → safe PvE simulation\n"
        "/editchar CHARACTER_KEY → edit a published character\n"
        "/playersearch NAME_OR_ID → owner/moderator player card search\n"
        "/cancel → cancel an active content wizard",
    ),
}


def guide_menu_markup() -> InlineKeyboardMarkup:
    keys = list(GUIDE_TOPICS)
    rows = []
    for index in range(0, len(keys), 2):
        rows.append([
            InlineKeyboardButton(GUIDE_TOPICS[key][0], callback_data=f"guide:{key}")
            for key in keys[index:index + 2]
        ])
    rows.append([InlineKeyboardButton("Complete PDF guide →", callback_data="guide:pdf")])
    rows.append([InlineKeyboardButton("← Main menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


async def send_guide_menu(message, edit: bool = False) -> None:
    text = (
        "<b>CapeVerse Guide Center</b>\n\n"
        "Choose a guide →\n"
        "Each section explains one part of the game.\n"
        "Use the PDF for the complete handbook."
    )
    if edit:
        await message.edit_text(text, parse_mode="html", reply_markup=guide_menu_markup())
    else:
        await message.reply_text(text, parse_mode="html", reply_markup=guide_menu_markup())


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
    moves: list[dict] | None = None,
    cooldowns: dict | None = None,
) -> InlineKeyboardMarkup:
    if finished:
        return InlineKeyboardMarkup([[InlineKeyboardButton("← Main menu", callback_data="menu:home")]])
    names = move_names or {}
    available = moves or [
        {"key": "signature", "name": names.get("signature", "Signature")},
        {"key": "utility", "name": names.get("utility", "Utility")},
        {"key": "ultimate", "name": names.get("ultimate", "Ultimate")},
    ]
    cooldowns = cooldowns or {}
    buttons = []
    for move in available:
        remaining = int(cooldowns.get(move["key"], 0))
        suffix = f" · CD {remaining}" if remaining else " →"
        buttons.append(InlineKeyboardButton(
            f"{str(move.get('name', 'Move'))[:20]}{suffix}",
            callback_data=f"battle:{battle_id}:{move['key']}",
        ))
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("← Main menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def _battle_text(battle: dict, enemy_name: str | None = None) -> str:
    latest = battle.get("log", [])[-1:] if battle else []
    log_line = f"\n\n<blockquote>{latest[0]}</blockquote>" if latest else ""
    enemy_hp = int(battle.get("enemy_hp", 0))
    enemy_max = max(1, int(battle.get("enemy_max_hp", enemy_hp or 100)))
    player_hp = int(battle.get("player_hp", 0))
    player_max = max(1, int(battle.get("player_max_hp", 100)))

    def bar(current: int, maximum: int) -> str:
        filled = max(0, min(10, round((current / maximum) * 10)))
        return "▰" * filled + "▱" * (10 - filled)

    return (
        f"<b>{battle.get('stage', 'Battle')}</b>\n\n"
        f"<b>{enemy_name or battle.get('enemy_name', 'Threat')}</b>\n"
        f"Level {battle.get('enemy_level', 1)} · {bar(enemy_hp, enemy_max)}  {enemy_hp}/{enemy_max} HP\n\n"
        f"<b>{battle.get('actor_name', 'Your hero')}</b>\n"
        f"Level {battle.get('actor_level', 1)} · {bar(player_hp, player_max)}  {player_hp}/{player_max} HP\n\n"
        f"Turn {battle.get('turn', 1)} → choose a move{log_line}"
    )


def _all_moves(hero: dict) -> list[dict]:
    move_sets = hero.get("move_sets") or {}
    moves: list[dict] = []
    for category in ("normal", "defense", "special"):
        for move in move_sets.get(category, []):
            moves.append({**move, "category": category})
    if moves:
        return moves
    return [
        {"category": "normal", "name": hero.get("ability_signature", "Signature Move"), "description": "", "damage": hero.get("signature_damage", 24), "unlock_level": 1, "cooldown": 0},
        {"category": "defense", "name": hero.get("ability_utility", "Guard"), "description": "", "damage": hero.get("utility_damage", 0), "unlock_level": 1, "cooldown": 1},
        {"category": "special", "name": hero.get("ability_ultimate", "Ultimate"), "description": "", "damage": hero.get("ultimate_damage", 38), "unlock_level": 1, "cooldown": 2},
    ]


def _character_detail_text(hero: dict, owned: dict | None = None) -> str:
    owned = owned or {}
    level = int(owned.get("level", 1))
    xp = int(owned.get("xp", 0))
    next_xp = max(100, level * 100)
    grouped: dict[str, list[str]] = {"normal": [], "defense": [], "special": []}
    for move in _all_moves(hero):
        unlock = int(move.get("unlock_level", 1))
        state = "UNLOCKED" if owned and level >= unlock else f"LOCKED · Lv {unlock}"
        if not owned:
            state = f"Unlock Lv {unlock}"
        grouped[move["category"]].append(
            f"· <b>{escape(str(move.get('name', 'Move')))}</b> · {move.get('damage', 0)} damage · CD {move.get('cooldown', 0)}\n"
            f"  {state} · {escape(str(move.get('description', ''))[:180])}\n"
            f"  Effect → {escape(str(move.get('effect', 'none'))[:100])}"
        )
    move_text = "\n\n".join(
        f"<b>{category.title()} moves</b>\n" + ("\n".join(grouped[category]) or "No moves")
        for category in ("normal", "defense", "special")
    )
    licensed = str(hero.get("source", "")).startswith("Licensed")
    if licensed:
        concepts = hero.get("research_concepts", [])
        evolution = "Licensed forms and suits use Research Archive entries, not evolution."
        if concepts:
            evolution += "\n" + "\n".join(
                f"· Research → {escape(str(item.get('name', 'Archive entry')))} · Lv {item.get('unlock_level', 1)}"
                for item in concepts[:4]
            )
    else:
        evolution = (
            "Evolved"
            if owned.get("evolved")
            else f"Base form · requires Lv 10 and 3 stars ({level}/10 · {owned.get('stars', 0)}/3)"
            if owned
            else "Evolution progress begins when collected"
        )
        concepts = hero.get("evolution_concepts", [])
        if concepts:
            evolution += "\n" + "\n".join(
                f"· {escape(str(item.get('name', 'Evolution')))} · Lv {item.get('unlock_level', 10)}"
                for item in concepts[:4]
            )
    ownership = (
        f"Character level → <b>{level}</b> · XP {xp}/{next_xp}\nStars → {owned.get('stars', 0)}\n"
        if owned else "<i>Codex preview · not collected</i>\n"
    )
    return (
        f"<b>{escape(str(hero.get('name', 'Unknown character')))}</b> · {escape(str(hero.get('codename', '')))}\n"
        f"{escape(str(hero.get('origin_type', 'Unknown type')))} · {escape(str(hero.get('rarity', 'Common')))} · {escape(str(hero.get('role', 'Unknown role')))}\n"
        f"Universe → {escape(str(hero.get('universe', 'Unknown')))}\n"
        f"Place → {escape(str(hero.get('place', 'Unknown')))}\n"
        f"Faction → {escape(str(hero.get('faction', 'None')))}\n\n"
        f"{ownership}"
        f"Evolution → {evolution}\n\n"
        f"{escape(str(hero.get('description', 'No story available.'))[:700])}\n\n"
        f"{move_text}"
    )


def _find_character(query: str, telegram_id: int) -> tuple[dict | None, dict | None]:
    query_lower = query.strip().lower()
    owned_list = list_owned_heroes(telegram_id)
    for owned in owned_list:
        if query_lower in {str(owned.get("hero_key", "")).lower(), str(owned.get("name", "")).lower()}:
            return get_hero(owned["hero_key"]), owned
    for hero in list_heroes():
        fields = {str(hero.get(key, "")).lower() for key in ("hero_key", "name", "codename")}
        if query_lower in fields or any(query_lower in field for field in fields):
            return hero, get_owned_hero(telegram_id, hero["hero_key"])
    return None, None


def _character_list_markup(telegram_id: int) -> InlineKeyboardMarkup:
    heroes = list_owned_heroes(telegram_id)[:12]
    rows = [
        [
            InlineKeyboardButton(
                f"{hero.get('name', 'Hero')} · Lv {hero.get('level', 1)}",
                callback_data=f"mychar:view:{hero['hero_key']}",
            )
        ]
        for hero in heroes
    ]
    rows.append([InlineKeyboardButton("← Main menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def _global_character_markup() -> InlineKeyboardMarkup:
    heroes = list_heroes()[:12]
    rows = []
    for index in range(0, len(heroes), 2):
        rows.append([
            InlineKeyboardButton(
                f"{rarity_mark(hero.get('rarity', 'Common'))} {hero.get('name', 'Character')[:18]}",
                callback_data=f"char:view:{hero['hero_key']}",
            )
            for hero in heroes[index:index + 2]
        ])
    rows.append([InlineKeyboardButton("← Main menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def _character_actions(hero: dict, owned: dict | None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("Full stats & moves →", callback_data=f"char:stats:{hero['hero_key']}")]]
    if str(hero.get("source", "")).startswith("Licensed"):
        rows.append([InlineKeyboardButton("Research archive →", callback_data=f"char:research:{hero['hero_key']}")])
    elif owned and not owned.get("evolved"):
        rows.append([InlineKeyboardButton("Evolution guide / evolve →", callback_data=f"char:evolve:{hero['hero_key']}")])
    if owned:
        rows.append([InlineKeyboardButton("View my copy →", callback_data=f"mychar:view:{hero['hero_key']}")])
    rows.append([InlineKeyboardButton("Global codex", callback_data="char:global")])
    rows.append([InlineKeyboardButton("My characters", callback_data="mychar:list")])
    return InlineKeyboardMarkup(rows)


def _inventory_text(telegram_id: int) -> str:
    inventory = inventory_summary(telegram_id)
    profile = get_profile(telegram_id) or {}
    owner_name = escape(str(profile.get("first_name", "Player")))
    return (
        f"<b>Inventory</b>\nOwner → <b>{owner_name}</b>\n\n"
        "<b>Wallet</b>\n"
        f"Cape Credits → <b>{inventory['credits']}</b>\n"
        f"Signal Shards → <b>{inventory['signal_shards']}</b>\n"
        f"Prism Cores → <b>{inventory['prism_cores']}</b>\n"
        f"Patrol Intel → <b>{inventory['patrol_intel']}</b>\n\n"
        "<b>Collection</b>\n"
        f"Owned characters → {inventory['heroes']}\n"
        f"Relics → {inventory['relics']}\n"
        f"Research archives → {inventory['research']}\n\n"
        "Daily and weekly rewards appear below."
    )


def _character_card_caption(hero: dict, owned: dict | None) -> str:
    if owned:
        return (
            f"<b>{escape(str(hero.get('name', 'Character')))}</b>\n"
            f"{escape(str(hero.get('codename', '')))} · Level {owned.get('level', 1)} · ★ {owned.get('stars', 0)}\n"
            f"{escape(str(hero.get('origin_type', 'Unknown type')))} · {escape(str(hero.get('rarity', 'Common')))}\n\n"
            f"{escape(str(hero.get('description', 'No story available.'))[:520])}\n\n"
            "Full progression details are shown below."
        )
    return (
        f"<b>{escape(str(hero.get('name', 'Character')))}</b>\n"
        f"{escape(str(hero.get('codename', '')))} · Global Codex\n"
        f"{escape(str(hero.get('origin_type', 'Unknown type')))} · {escape(str(hero.get('rarity', 'Common')))}\n\n"
        f"{escape(str(hero.get('description', 'No story available.'))[:600])}"
    )


async def _send_global_character(message, hero: dict, telegram_id: int) -> None:
    owned = get_owned_hero(telegram_id, hero["hero_key"])
    photo = hero.get("image_url")
    if photo:
        try:
            await message.reply_photo(
                photo=photo,
                caption=_character_card_caption(hero, None),
                parse_mode="html",
                reply_markup=_character_actions(hero, owned),
            )
            return
        except Exception:
            pass
    card = generate_character_card(hero, None)
    await message.reply_photo(
        photo=str(card),
        caption=_character_card_caption(hero, None),
        parse_mode="html",
        reply_markup=_character_actions(hero, owned),
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
    await send_guide_menu(message)


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


async def char_command(client, message):
    _player(message)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 1:
        await message.reply_text(
            "<b>Global Character Codex</b>\n\n"
            "Choose a published character or send:\n"
            "<code>/char character name</code>\n\n"
            "This shows global story, artwork, moves, and research/evolution information.",
            parse_mode="html",
            reply_markup=_global_character_markup(),
        )
        return
    hero, _ = _find_character(parts[1], message.from_user.id)
    if not hero:
        await message.reply_text("<b>Character not found</b>\n\nSearch using the exact name, codename, or character key.", parse_mode="html")
        return
    await _send_global_character(message, hero, message.from_user.id)


async def mychar_command(client, message):
    _player(message)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 1:
        await message.reply_text(
            "<b>My Characters</b>\n\nChoose your owned character or send:\n"
            "<code>/mychar character name</code>",
            parse_mode="html",
            reply_markup=_character_list_markup(message.from_user.id),
        )
        return
    hero, owned = _find_character(parts[1], message.from_user.id)
    if not hero or not owned:
        await message.reply_text("<b>Owned character not found</b>\n\nUse /char NAME for global codex data.", parse_mode="html")
        return
    card = generate_character_card(hero, owned)
    await message.reply_photo(
        photo=str(card),
        caption=_character_card_caption(hero, owned),
        parse_mode="html",
        reply_markup=_character_actions(hero, owned),
    )
    await message.reply_text(_character_detail_text(hero, owned), parse_mode="html")


async def inventory_command(client, message):
    _player(message)
    await message.reply_text(
        _inventory_text(message.from_user.id),
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Daily reward", callback_data="reward:daily"),
                InlineKeyboardButton("Weekly reward", callback_data="reward:weekly"),
            ],
            [
                InlineKeyboardButton("My characters", callback_data="mychar:list"),
                InlineKeyboardButton("Relics", callback_data="menu:relics"),
            ],
            [InlineKeyboardButton("← Main menu", callback_data="menu:home")],
        ]),
    )


async def _claim_reward_message(message, telegram_id: int, period: str, edit: bool = False) -> None:
    result = claim_timed_reward(telegram_id, period)
    if not result["ok"]:
        next_claim = result.get("next_claim_at")
        when = next_claim.strftime("%d %b %Y · %H:%M UTC") if next_claim else "later"
        text = f"<b>{period.title()} reward already claimed</b>\n\nNext claim → {when}"
        if edit:
            await _edit_callback(message, text, back_markup())
        else:
            await message.reply_text(text, parse_mode="html", reply_markup=back_markup())
        return
    reward = result["rewards"]
    text = (
        f"<b>{period.title()} signal claimed</b>\n\n"
        f"Cape Credits → +{reward['credits']}\n"
        f"Patrol Intel → +{reward['patrol_intel']}\n"
        f"Signal Shards → +{reward['signal_shards']}\n"
        f"Player XP → +{reward['xp']}\n"
        f"Streak → {result['streak']}"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Inventory", callback_data="menu:inventory")]])
    if edit:
        await _edit_callback(message, text, markup)
    else:
        await message.reply_text(text, parse_mode="html", reply_markup=markup)


async def _edit_callback(message, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    if getattr(message, "photo", None):
        await message.edit_caption(caption=text[:1024], parse_mode="html", reply_markup=markup)
    else:
        await message.edit_text(text, parse_mode="html", reply_markup=markup)


async def daily_command(client, message):
    _player(message)
    await _claim_reward_message(message, message.from_user.id, "daily")


async def weekly_command(client, message):
    _player(message)
    await _claim_reward_message(message, message.from_user.id, "weekly")


async def callback_handler(client, callback_query):
    data = callback_query.data or ""
    if data.startswith(("admin:", "wizard:")):
        return
    user_id = callback_query.from_user.id
    await callback_query.answer()

    if data in {"char:list", "mychar:list"}:
        await _edit_callback(
            callback_query.message,
            "<b>My characters</b>\n\nChoose a character →",
            _character_list_markup(user_id),
        )
        return
    if data == "char:global":
        await _edit_callback(
            callback_query.message,
            "<b>Global Character Codex</b>\n\nChoose a published character →",
            _global_character_markup(),
        )
        return
    if data.startswith("char:view:"):
        hero_key = data.split(":", 2)[2]
        hero = get_hero(hero_key)
        owned = get_owned_hero(user_id, hero_key)
        if not hero:
            await callback_query.message.reply_text("<b>Character unavailable</b>", parse_mode="html")
            return
        licensed = str(hero.get("source", "")).startswith("Licensed")
        progression = "Research Archive" if licensed else "Evolution path"
        await _edit_callback(
            callback_query.message,
            f"{_character_card_caption(hero, None)}\n\n{_character_detail_text(hero, owned)}\n\nProgression → {progression}",
            _character_actions(hero, owned),
        )
        return
    if data.startswith("mychar:view:"):
        hero_key = data.split(":", 2)[2]
        hero = get_hero(hero_key)
        owned = get_owned_hero(user_id, hero_key)
        if not hero or not owned:
            await callback_query.message.reply_text("<b>Owned character unavailable</b>", parse_mode="html")
            return
        card = generate_character_card(hero, owned)
        await _edit_callback(
            callback_query.message,
            f"{_character_card_caption(hero, owned)}\n\n{_character_detail_text(hero, owned)}",
            _character_actions(hero, owned),
        )
        return
    if data.startswith("char:stats:"):
        hero_key = data.split(":", 2)[2]
        hero = get_hero(hero_key)
        if not hero:
            return
        owned = get_owned_hero(user_id, hero_key)
        await _edit_callback(callback_query.message, _character_detail_text(hero, owned), _character_actions(hero, owned))
        return
    if data.startswith("char:research:"):
        hero_key = data.split(":", 2)[2]
        result = research_character(user_id, hero_key)
        if not result["ok"]:
            await _edit_callback(callback_query.message, f"<b>Research unavailable</b>\n\n{result['reason']}", back_markup())
            return
        hero = result["hero"]
        status = "New archive unlocked" if result["new"] else "Archive already researched"
        concepts = hero.get("research_concepts", [])
        concept_text = "\n".join(
            f"· <b>{escape(str(item.get('name', 'Suit archive')))}</b>\n  {escape(str(item.get('description', ''))[:220])}"
            for item in concepts[:4]
        ) or "The owner has not added suit/form research entries yet."
        await _edit_callback(
            callback_query.message,
            f"<b>{status}</b>\n\n{escape(str(hero.get('name', hero_key)))}\n\n{concept_text}\n\n"
            "Licensed suits and forms are documented as research; they do not replace character evolution.",
            back_markup(),
        )
        await log_event(client, "Character research", f"{hero.get('name', hero_key)} archive viewed", user_id)
        return
    if data.startswith("char:evolve:"):
        hero_key = data.split(":", 2)[2]
        hero = get_hero(hero_key) or {}
        if str(hero.get("source", "")).startswith("Licensed"):
            await _edit_callback(
                callback_query.message,
                "<b>Use Research Archive</b>\n\nLicensed suits and documented forms are research entries, not evolutions.",
                back_markup(),
            )
            return
        result = evolve_character(user_id, hero_key)
        if not result["ok"]:
            await _edit_callback(callback_query.message, f"<b>Evolution unavailable</b>\n\n{result['reason']}", back_markup())
            return
        owned = result["character"]
        await _edit_callback(
            callback_query.message,
            f"<b>Evolution complete</b>\n\n{escape(str(hero.get('name', hero_key)))} reached an evolved form.\n"
            "The character card and battle identity now show the evolution.",
            back_markup(),
        )
        await log_event(client, "Character evolution", f"{hero.get('name', hero_key)} evolved", user_id)
        return

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
                "<b>Default inventory</b>\n"
                "Cape Credits → 500\nSignal Shards → 2\nPatrol Intel → 5\nPrism Cores → 0\n\n"
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
            "<b>Default inventory</b>\n"
            "Cape Credits → 500\nSignal Shards → 2\nPatrol Intel → 5\nPrism Cores → 0\n\n"
            "Team 1 is ready. Choose your next step →",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Open inventory →", callback_data="menu:inventory")],
                    [InlineKeyboardButton("Begin first battle →", callback_data="menu:battle")],
                    [InlineKeyboardButton("Main menu", callback_data="menu:home")],
                ]
            ),
        )
        return

    if data == "menu:home":
        await _edit_callback(
            callback_query.message,
            "<b>CapeVerse</b>\n\nChoose your next move →",
            main_menu_markup(),
        )
        return
    if data == "menu:profile":
        await show_profile(callback_query.message, edit=True, telegram_id=user_id)
        return
    if data == "menu:inventory":
        await _edit_callback(
            callback_query.message,
            _inventory_text(user_id),
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Daily reward", callback_data="reward:daily"),
                    InlineKeyboardButton("Weekly reward", callback_data="reward:weekly"),
                ],
                [InlineKeyboardButton("My characters", callback_data="mychar:list")],
                [InlineKeyboardButton("← Main menu", callback_data="menu:home")],
            ]),
        )
        return
    if data in {"reward:daily", "reward:weekly"}:
        await _claim_reward_message(callback_query.message, user_id, data.split(":", 1)[1], edit=True)
        return
    if data == "menu:guide":
        await send_guide_menu(callback_query.message, edit=True)
        return
    if data == "guide:pdf":
        await send_guide(callback_query.message)
        return
    if data.startswith("guide:"):
        topic = data.split(":", 1)[1]
        entry = GUIDE_TOPICS.get(topic)
        if not entry:
            return
        await callback_query.message.edit_text(
            entry[1],
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("← All guides", callback_data="menu:guide")],
                [InlineKeyboardButton("Main menu", callback_data="menu:home")],
            ]),
        )
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
        text = f"<b>Patrol complete</b>\n\n+ {result.get('credits', 0)} Cape Credits\n+ {result.get('xp', 0)} player XP · Level {result.get('level', 1)}\n→ The city keeps moving." if result["ok"] else f"<b>Patrol unavailable</b>\n\n{result['reason']}"
        await callback_query.message.edit_text(text, parse_mode="html", reply_markup=back_markup())
        return
    if data.startswith("mission:case:"):
        alignment = data.split(":", 2)[2]
        result = complete_case(user_id, alignment)
        text = (
            f"<b>Case File resolved</b>\n\nChoice → {result['alignment']}\nReward → +{result['credits']} Cape Credits\n"
            f"Player XP → +{result.get('xp', 0)} · Level {result.get('level', 1)}\nAlignment updated →"
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
            "enemy_max_hp": battle_info["enemy_hp"],
            "player_hp": battle_info["player_hp"],
            "player_max_hp": battle_info["player_hp"],
            "turn": 1,
            "actor_name": battle_info["actor_name"],
            "actor_level": battle_info["actor_level"],
            "enemy_level": battle_info["enemy_level"],
        }
        await callback_query.message.edit_text(
            _battle_text(battle, battle_info["enemy_name"]),
            parse_mode="html",
            reply_markup=_battle_markup(
                battle_info["id"],
                mode=mode,
                move_names=battle_info["move_names"],
                nemesis_available=battle_info["nemesis_available"],
                moves=battle_info["moves"],
            ),
        )
        return
    if data == "menu:arena":
        battle_info = start_arena(user_id)
        if not battle_info["ok"]:
            await callback_query.message.edit_text(f"<b>Arena unavailable</b>\n\n{battle_info['reason']}", parse_mode="html", reply_markup=back_markup())
            return
        battle = {"stage": "Sanctioned Bout", "enemy_hp": battle_info["enemy_hp"], "enemy_max_hp": battle_info["enemy_hp"], "player_hp": battle_info["player_hp"], "player_max_hp": battle_info["player_hp"], "turn": 1, "actor_level": battle_info["actor_level"], "enemy_level": battle_info["enemy_level"]}
        battle["actor_name"] = battle_info["actor_name"]
        await callback_query.message.edit_text(_battle_text(battle, battle_info["enemy_name"]), parse_mode="html", reply_markup=_battle_markup(battle_info["id"], mode="arena", move_names=battle_info["move_names"], moves=battle_info["moves"]))
        return
    if data == "menu:rift":
        profile = get_profile(user_id) or {}
        floor = int(profile.get("rift_floor", 1))
        battle_info = start_rift(user_id, floor)
        if not battle_info["ok"]:
            await callback_query.message.edit_text(f"<b>The Rift is unavailable</b>\n\n{battle_info['reason']}", parse_mode="html", reply_markup=back_markup())
            return
        battle = {"stage": f"The Rift · Floor {floor}", "enemy_hp": battle_info["enemy_hp"], "enemy_max_hp": battle_info["enemy_hp"], "player_hp": battle_info["player_hp"], "player_max_hp": battle_info["player_hp"], "turn": 1, "actor_level": battle_info["actor_level"], "enemy_level": battle_info["enemy_level"]}
        battle["actor_name"] = battle_info["actor_name"]
        await callback_query.message.edit_text(_battle_text(battle, battle_info["enemy_name"]), parse_mode="html", reply_markup=_battle_markup(battle_info["id"], mode="rift", move_names=battle_info["move_names"], nemesis_available=battle_info["nemesis_available"], moves=battle_info["moves"]))
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
            "enemy_max_hp": battle_info["enemy_hp"],
            "player_hp": battle_info["player_hp"],
            "player_max_hp": battle_info["player_hp"],
            "turn": 1,
            "actor_name": battle_info["actor_name"],
            "actor_level": battle_info["actor_level"],
            "enemy_level": battle_info["enemy_level"],
        }
        await callback_query.message.edit_text(
            _battle_text(battle, battle_info["enemy_name"]),
            parse_mode="html",
            reply_markup=_battle_markup(
                battle_info["id"],
                mode="event",
                move_names=battle_info["move_names"],
                nemesis_available=battle_info["nemesis_available"],
                moves=battle_info["moves"],
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
        result_line = "\n\n<b>Victory → reward granted</b>" if battle["status"] == "won" else "\n\n<b>Defeat → regroup and try again</b>" if battle["status"] == "lost" else ""
        await callback_query.message.edit_text(
            _battle_text(battle) + result_line,
            parse_mode="html",
            reply_markup=_battle_markup(
                battle_id,
                finished,
                battle["mode"],
                battle.get("move_names", {}),
                bool(battle.get("nemesis_available")),
                battle.get("moves", []),
                battle.get("cooldowns", {}),
            ),
        )
        if finished:
            await log_event(client, "Battle result", f"{battle['mode']} → {battle['status']} against {battle.get('enemy_name', 'threat')}", user_id)


def register(client) -> None:
    client.add_handler(MessageHandler(start_command, filters.command("start")))
    client.add_handler(MessageHandler(guide_command, filters.command("guide")))
    client.add_handler(MessageHandler(menu_command, filters.command(["main", "menu", "help"])))
    client.add_handler(MessageHandler(profile_command, filters.command("profile")))
    client.add_handler(MessageHandler(char_command, filters.command("char")))
    client.add_handler(MessageHandler(mychar_command, filters.command("mychar")))
    client.add_handler(MessageHandler(inventory_command, filters.command("inventory")))
    client.add_handler(MessageHandler(daily_command, filters.command("daily")))
    client.add_handler(MessageHandler(weekly_command, filters.command("weekly")))
    client.add_handler(CallbackQueryHandler(callback_handler))