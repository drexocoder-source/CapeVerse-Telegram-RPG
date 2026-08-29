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
    image = Image.new("RGB", (1200, 675), "#0b1426")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 1200, 14), fill="#63d2bf")
    draw.ellipse((950, -180, 1350, 220), fill="#182a45")
    draw.ellipse((1020, 420, 1340, 740), fill="#12213a")
    draw.text((74, 68), "CAPEVERSE", fill="#63d2bf", font=_font(23, True))
    draw.text((74, 122), name[:22], fill="#f4f7fb", font=_font(50, True))
    draw.text((76, 190), "PLAYER PROFILE", fill="#9cacc2", font=_font(17, True))
    draw.line((76, 244, 1125, 244), fill="#263a56", width=2)

    items = [
        ("ORIGIN", origin),
        ("RATING", str(rating)),
        ("HEROES", str(len(heroes))),
        ("TEAM", f"{team_count}/3"),
        ("SYNERGY", f"+{synergy}%"),
        ("RIFT", f"FLOOR {profile.get('rift_floor', 1)}"),
    ]
    for index, (label, value) in enumerate(items):
        x = 76 + (index % 3) * 350
        y = 292 + (index // 3) * 125
        draw.text((x, y), label, fill="#7d93ae", font=_font(15, True))
        draw.text((x, y + 30), value[:20], fill="#f4f7fb", font=_font(27, True))

    draw.text((76, 590), "Collect. Build. Choose your signal.", fill="#63d2bf", font=_font(18))
    path = CARD_DIR / f"{profile.get('telegram_id', 'player')}.png"
    image.save(path, "PNG")
    return path