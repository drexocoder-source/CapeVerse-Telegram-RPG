from typing import Any

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def rarity_mark(rarity: str) -> str:
    return {
        "Common": "·",
        "Rare": "◆",
        "Epic": "◆◆",
        "Legendary": "◆◆◆",
        "Mythic": "◆◆◆◆",
    }.get(rarity, "·")


def origin_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚡ Enhanced", callback_data="origin:enhanced"),
                InlineKeyboardButton("Tech", callback_data="origin:tech"),
            ],
            [InlineKeyboardButton("Mystic", callback_data="origin:mystic")],
        ]
    )


def main_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Battle →", callback_data="menu:battle"),
                InlineKeyboardButton("Heroes", callback_data="menu:heroes"),
            ],
            [
                InlineKeyboardButton("Recruit", callback_data="menu:recruit"),
                InlineKeyboardButton("Relics", callback_data="menu:relics"),
            ],
            [
                InlineKeyboardButton("Team", callback_data="menu:team"),
                InlineKeyboardButton("Missions", callback_data="menu:missions"),
            ],
            [
                InlineKeyboardButton("Arena", callback_data="menu:arena"),
                InlineKeyboardButton("The Rift", callback_data="menu:rift"),
            ],
            [InlineKeyboardButton("Events →", callback_data="menu:events")],
            [
                InlineKeyboardButton("Profile", callback_data="menu:profile"),
                InlineKeyboardButton("Character card", callback_data="char:list"),
            ],
            [InlineKeyboardButton("Guide", callback_data="menu:guide")],
        ]
    )


def back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Back to menu", callback_data="menu:home")]])


def profile_text(profile: dict[str, Any], owned_count: int, team_count: int, synergy: int) -> str:
    name = profile.get("first_name") or profile.get("username") or "Player"
    origin = profile.get("origin") or "Not chosen"
    rating = profile.get("rating", 1000)
    floor = profile.get("rift_floor", 1)
    level = int(profile.get("level", 1))
    xp = int(profile.get("xp", 0))
    next_xp = max(100, level * 100)
    return (
        f"<b>{name}</b>\n"
        f"<i>CapeVerse player profile</i>\n\n"
        f"Level   →  <b>{level}</b> · XP {xp}/{next_xp}\n"
        f"Origin  →  <b>{origin}</b>\n"
        f"Rank    →  <b>{rating}</b>\n"
        f"Rift    →  Floor {floor}\n"
        f"Heroes  →  {owned_count}\n"
        f"Team    →  {team_count}/3 active\n"
        f"Synergy →  +{synergy}%\n\n"
        f"<b>Wallet</b>\n"
        f"Cape Credits  →  {profile.get('credits', 0)}\n"
        f"Signal Shards →  {profile.get('signal_shards', 0)}\n"
        f"Prism Cores   →  {profile.get('prism_cores', 0)}\n"
        f"Patrol Intel  →  {profile.get('patrol_intel', 0)}"
    )