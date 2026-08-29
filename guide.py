from pathlib import Path


GUIDE_PATH = Path(__file__).resolve().parent / "capeverse_player_guide.pdf"


def ensure_guide_pdf() -> Path:
    if GUIDE_PATH.exists():
        return GUIDE_PATH

    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "CapeTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=29,
        textColor="#10243E",
        alignment=TA_LEFT,
        spaceAfter=8,
    )
    heading = ParagraphStyle(
        "CapeHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor="#0D6E8A",
        spaceBefore=11,
        spaceAfter=5,
    )
    body = ParagraphStyle(
        "CapeBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor="#253247",
        spaceAfter=5,
    )

    story = [
        Paragraph("CapeVerse", title),
        Paragraph("Player Guide · First Signal", body),
        Paragraph("A superhero collection and battle adventure built around original worlds, strategic teams, and evolving heroes.", body),
        Paragraph("Start here", heading),
        Paragraph("Use /start to create your account. Choose Enhanced, Tech, or Mystic to receive your starter hero and permanent Origin passive. Your starter automatically joins Team 1.", body),
        Paragraph("Collect heroes", heading),
        Paragraph("Heroes are found through the Recruitment Beacon, Case Files, Patrol rewards, Rift bosses, seasonal Events, and Hero Fragments. Duplicate pulls become fragments and star-up materials.", body),
        Paragraph("Build your team", heading),
        Paragraph("A battle team has three heroes. Combine roles, factions, alignments, and universes to unlock Synergy bonuses. Save different teams later for Story, Arena, Rift, and Events.", body),
        Paragraph("Battle flow", heading),
        Paragraph("Choose a target → use Signature, Utility, or Ultimate → read the result → choose your next action. Battles are server-controlled, so rewards and damage cannot be edited by the player.", body),
        Paragraph("Currencies", heading),
        Paragraph("Cape Credits pay for progression. Signal Shards power Beacon pulls. Prism Cores are premium currency. Patrol Intel starts missions. Hero Fragments unlock and improve specific heroes.", body),
        Paragraph("The five first chapters", heading),
        Paragraph("1. Origin and first battle → 2. Recruitment and relics → 3. Patrols and Case Files → 4. Sanctioned Bouts Arena → 5. The Rift and Nemesis battles.", body),
        Paragraph("Fair play", heading),
        Paragraph("Show your Signal Boost progress before pulling. Do not share account access. Trades, when enabled, will use confirmation, expiry, and a visible tax. Relics are not tradeable.", body),
        Paragraph("Useful commands", heading),
        Paragraph("/start → begin or reopen the adventure<br/>/menu → return to the main menu<br/>/guide → receive this guide again<br/>/profile → view your player summary", body),
    ]

    document = SimpleDocTemplate(
        str(GUIDE_PATH),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="CapeVerse Player Guide",
        author="CapeVerse",
    )
    document.build(story)
    return GUIDE_PATH