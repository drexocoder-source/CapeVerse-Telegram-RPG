from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CARD_DIR = Path("data/profile_cards")


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def generate_profile_card(profile: dict[str, Any], heroes: list[dict[str, Any]], team_count: int, synergy: int) -> Path:
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    name = profile.get("first_name") or profile.get("username") or "Player"
    origin = profile.get("origin") or "Not chosen"
    rating = profile.get("rating", 1000)
    level = int(profile.get("level", 1))
    xp = int(profile.get("xp", 0))
    next_xp = max(100, level * 100)
    image = Image.new("RGB", (1200, 675), "#050b16")
    draw = ImageDraw.Draw(image)

    accent = "#69f0d1"
    draw.rectangle((0, 0, 1200, 16), fill=accent)
    draw.polygon([(0, 16), (585, 16), (390, 675), (0, 675)], fill="#0b1a2c")
    draw.polygon([(860, 0), (1200, 0), (1200, 675), (1010, 675)], fill="#101d32")
    draw.rounded_rectangle((54, 50, 1145, 625), radius=30, outline="#233954", width=3)
    draw.text((82, 70), "CAPEVERSE // SIGNAL DOSSIER", fill=accent, font=_font(20, True))
    draw.text((82, 118), name[:22], fill="#f7fbff", font=_font(49, True))
    draw.text((84, 183), f"ORIGIN {origin.upper()}  ·  ALIGNMENT {str(profile.get('alignment', 'Hero')).upper()}", fill="#91a7c4", font=_font(15, True))
    draw.line((82, 228, 800, 228), fill="#2a4565", width=2)

    featured = heroes[0] if heroes else {}
    featured_name = str(featured.get("name", "NO ACTIVE SIGNAL"))
    initials = "".join(word[:1] for word in featured_name.split()[:2]).upper() or "CV"
    draw.ellipse((865, 82, 1095, 312), fill="#132b42", outline=accent, width=5)
    initials_box = draw.textbbox((0, 0), initials, font=_font(64, True))
    initials_w = initials_box[2] - initials_box[0]
    draw.text((980 - initials_w / 2, 150), initials, fill="#f7fbff", font=_font(64, True))
    draw.text((865, 332), "FEATURED SIGNAL", fill="#718baa", font=_font(13, True))
    draw.text((865, 358), featured_name[:20], fill="#edf5ff", font=_font(21, True))

    items = [
        ("LEVEL", str(level)),
        ("ORIGIN", origin),
        ("RATING", str(rating)),
        ("HEROES", str(len(heroes))),
        ("TEAM", f"{team_count}/3"),
        ("RIFT", f"FLOOR {profile.get('rift_floor', 1)}"),
    ]
    for index, (label, value) in enumerate(items):
        x = 82 + (index % 3) * 245
        y = 265 + (index // 3) * 105
        draw.text((x, y), label, fill="#7d93ae", font=_font(15, True))
        draw.text((x, y + 30), value[:20], fill="#f4f7fb", font=_font(27, True))

    bar_x, bar_y, bar_w = 82, 505, 690
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + 18), radius=9, fill="#20344a")
    fill_w = round(bar_w * min(1, xp / next_xp))
    draw.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + 18), radius=9, fill="#66e3c4")
    draw.text((82, 535), f"XP {xp}/{next_xp}  ·  SYNERGY +{synergy}%", fill="#9cacc2", font=_font(16, True))
    draw.text((865, 425), "WALLET", fill="#718baa", font=_font(13, True))
    draw.text((865, 455), f"CR {profile.get('credits', 0)}", fill="#f1d77a", font=_font(20, True))
    draw.text((865, 490), f"SHARDS {profile.get('signal_shards', 0)}", fill="#91d9ff", font=_font(17, True))
    draw.text((865, 523), f"CORES {profile.get('prism_cores', 0)}", fill="#d6a8ff", font=_font(17, True))
    draw.text((82, 585), "VERSION 0.8  ·  COLLECT  /  RESEARCH  /  ASCEND", fill=accent, font=_font(16, True))
    path = CARD_DIR / f"{profile.get('telegram_id', 'player')}.png"
    image.save(path, "PNG")
    return path


def generate_character_card(hero: dict[str, Any], owned: dict[str, Any] | None = None) -> Path:
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    owned = owned or {}
    level = int(owned.get("level", 1))
    xp = int(owned.get("xp", 0))
    next_xp = max(100, level * 100)
    image = Image.new("RGB", (1200, 675), "#090f1d")
    draw = ImageDraw.Draw(image)
    accent = "#8be0ff" if hero.get("alignment") == "Hero" else "#e9a6ff"
    draw.rectangle((0, 0, 20, 675), fill=accent)
    draw.polygon([(650, 0), (1200, 0), (1200, 675), (900, 675)], fill="#121f35")
    draw.ellipse((880, 70, 1170, 360), outline=accent, width=6)
    draw.text((75, 55), str(hero.get("universe", "CAPEVERSE")).upper()[:22], fill=accent, font=_font(21, True))
    draw.text((75, 105), str(hero.get("name", "Unknown"))[:24], fill="#f5f8ff", font=_font(48, True))
    draw.text((78, 170), str(hero.get("codename", hero.get("origin_type", "Character")))[:35], fill="#9db0c9", font=_font(20))
    draw.line((75, 225, 780, 225), fill="#2a3b54", width=2)
    facts = [
        ("TYPE", hero.get("origin_type", "Unknown")),
        ("RARITY", hero.get("rarity", "Common")),
        ("ROLE", hero.get("role", "Unknown")),
        ("LEVEL", str(level) if owned else "CODEX"),
        ("STARS", str(owned.get("stars", 0)) if owned else "—"),
        ("EVOLUTION", "EVOLVED" if owned.get("evolved") else "BASE"),
    ]
    for index, (label, value) in enumerate(facts):
        x = 75 + (index % 3) * 245
        y = 270 + (index // 3) * 115
        draw.text((x, y), label, fill="#7188a6", font=_font(13, True))
        draw.text((x, y + 27), str(value)[:18], fill="#eef4ff", font=_font(22, True))
    if owned:
        draw.rounded_rectangle((75, 535, 775, 553), radius=9, fill="#22344b")
        fill_w = round(700 * min(1, xp / next_xp))
        draw.rounded_rectangle((75, 535, 75 + fill_w, 553), radius=9, fill=accent)
        draw.text((75, 570), f"CHARACTER XP  {xp}/{next_xp}", fill="#a8bad0", font=_font(16, True))
    draw.text((905, 377), "CAPEVERSE", fill=accent, font=_font(18, True))
    draw.text((905, 412), str(hero.get("place", "Unknown place"))[:20], fill="#dbe6f7", font=_font(17))
    path = CARD_DIR / f"character_{hero.get('hero_key', 'unknown')}_{owned.get('telegram_id', 'codex')}.png"
    image.save(path, "PNG")
    return path