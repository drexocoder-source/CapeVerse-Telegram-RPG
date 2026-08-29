from pathlib import Path


GUIDE_PATH = Path(__file__).resolve().parent / "capeverse_player_guide.pdf"


def ensure_guide_pdf() -> Path:
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
        Paragraph("Complete Player and Owner Handbook", body),
        Paragraph("CapeVerse is a Telegram superhero collection RPG built around owner-published original worlds, strategic teams, PvE, Arena, Rift encounters, relics, and boss events.", body),
        Paragraph("1 · Account and identity", heading),
        Paragraph("Use /start to create or reopen your account. CapeVerse displays your Telegram first name and uses your numeric Telegram ID as the permanent account identity. Usernames are not required and can change without affecting progress.", body),
        Paragraph("Choose Enhanced, Tech, or Mystic as your Origin. The choice grants a permanent passive. If the owner has published a starter for that Origin, the hero is granted and placed in Team 1 automatically.", body),
        Paragraph("2 · Main commands", heading),
        Paragraph("/start → create or reopen an account<br/>/main → open the game menu<br/>/inventory → view wallet, collection, relics, research, and rewards<br/>/profile → generate a visual player dossier<br/>/char NAME → global codex photo, story, moves, and research/evolution<br/>/mychar NAME → owned character level, XP, stars, and actions<br/>/daily and /weekly → timed rewards<br/>/guide → guide center", body),
        Paragraph("3 · Currencies and earning", heading),
        Paragraph("A new account begins with <b>500 Cape Credits</b>, <b>2 Signal Shards</b>, and <b>5 Patrol Intel</b>. <b>Prism Cores</b> are reserved for premium and special-event systems. Every balance change is written to the economy ledger.", body),
        Paragraph("<b>Patrol</b> spends 1 Patrol Intel and earns 120 Cape Credits. <b>Case File</b> spends 1 Patrol Intel and earns 90 Cape Credits for the Hero choice or 110 for the Vigilante/Antihero choice. <b>Normal battle</b> victory earns 75 Cape Credits. <b>Arena</b> victory earns 100 Cape Credits and 10 rating. <b>Rift</b> victory earns 150 Cape Credits and advances one floor. <b>Event bosses</b> pay the reward configured by the owner.", body),
        Paragraph("<b>Signal Shards</b> activate Recruitment Beacon pulls; one pull costs 1 Shard. <b>Relic forging</b> costs 100 Cape Credits. <b>Patrol Intel</b> is consumed by Patrol and Case File actions.", body),
        Paragraph("<b>Signal Boost</b> rises after ordinary recruitment results. When it reaches its threshold, the next pull is guaranteed to use the high-rarity pool and the meter resets.", body),
        Paragraph("4 · Heroes, universes, and places", heading),
        Paragraph("Every hero has a name, codename, character type, source, rights status, universe, place, faction, role, rarity, alignment, image, story, and categorized combat moves. Character type can be Human, Enhanced Human, Tech-Enhanced, Mystic, Alien, or a custom type.", body),
        Paragraph("The owner creates all heroes. Universe buttons include MCU, DCU, Bhoomi-1, and CapeVerse, with an option to type another universe. Place is always typed freely as a city, district, planet, realm, or any other place name. There are no hardcoded starter heroes. A hero can be marked as the Enhanced, Tech, or Mystic starter during guided creation.", body),
        Paragraph("5 · Teams and synergy", heading),
        Paragraph("Team 1 supports up to three owned heroes. The first active member performs the current battle actions. Universe variety contributes to the displayed synergy value. Future team editing can expand this into mode-specific squads.", body),
        Paragraph("6 · Recruitment Beacon", heading),
        Paragraph("One pull costs one Signal Shard. Published heroes form the recruitment pool. A new result joins the collection; duplicate pulls increase that hero's star count. Signal Boost rises by 10 after ordinary pulls. At 90, the next result uses the Epic, Legendary, or Mythic pool and the meter resets.", body),
        Paragraph("7 · XP, move unlocks, and evolution", heading),
        Paragraph("Players and characters level separately. Patrol grants 15 player XP, Case Files grant 20 player XP, and battle victories grant 30 to 50 player XP. The active character also gains battle XP. The XP requirement for the next level is current level × 100.", body),
        Paragraph("Moves unlock at their configured character level. Locked moves are visible in /mychar but do not appear in battle. Original CapeVerse characters may evolve at level 10 with 3 stars. Licensed suit generations and documented forms are Research Archive entries, not evolutions.", body),
        Paragraph("8 · Battle rules", heading),
        Paragraph("Moves are grouped into Normal, Defense, and Special categories. Defense moves reduce the incoming counterattack. Special moves are stronger and may unlock later or have longer cooldowns. A Nemesis move appears only when the active hero is linked to the current villain. Damage and rewards are calculated by the server.", body),
        Paragraph("Battle screens show both names, ten-segment HP bars, exact current and maximum HP, turn number, the latest move result, and available move buttons. Victory rewards are granted immediately and recorded in the ledger.", body),
        Paragraph("9 · PvE, Arena, and Rift", heading),
        Paragraph("<b>Normal enemies</b> power repeatable street operations. <b>Villains</b> power stronger hunts and Rift encounters. <b>Arena</b> uses another registered player's identity as the opposing captain. <b>Rift</b> victories grant higher rewards and increase the player's floor.", body),
        Paragraph("10 · Missions and alignment", heading),
        Paragraph("Patrols grant quick Cape Credits. Case Files consume Patrol Intel and offer choices such as protecting civilians or pursuing a threat. These choices update the player's Hero or Vigilante alignment and grant configured rewards.", body),
        Paragraph("11 · Relics", heading),
        Paragraph("Forging costs 100 Cape Credits. A relic has a slot, rarity, set name, base stat, substat, level, and equipped state. Relics remain in the player's permanent inventory.", body),
        Paragraph("12 · Events", heading),
        Paragraph("An event requires a published villain or event boss. The owner links that boss to an event and sets its description and Cape Credit reward. Players can then enter the boss battle from Events.", body),
        Paragraph("13 · Owner and moderator commands", heading),
        Paragraph("/owner → owner control panel<br/>/addmod → add a moderator<br/>/pending → review submissions<br/>/submithero → guided hero creation<br/>/submitvillain → guided enemy creation<br/>/editchar CHARACTER_KEY → edit a published character<br/>/playersearch NAME_OR_ID → view a player progression card<br/>/submitevent → event submission<br/>/test → deterministic PvE simulation<br/>/cancel → cancel a content wizard<br/>/adminhelp → admin instructions", body),
        Paragraph("14 · Guided content creation and AI", heading),
        Paragraph("The hero and villain wizards ask for the character story and a separate move-direction brief covering style, visuals, limits, personality, and tactics. OpenRouter analyzes the complete record to propose original balanced moves, effects, unlocks, difficulty, and original evolution concepts or licensed research topics. Each move category may contain one, two, three, or more moves, and the AI chooses the count naturally. AI output can be regenerated or edited and always remains a draft pending owner review.", body),
        Paragraph("Version 0.8 rewards", heading),
        Paragraph("New players receive 500 Cape Credits, 2 Signal Shards, 5 Patrol Intel, and 0 Prism Cores. Daily and weekly rewards use persistent claim timers and streak protection. Use /inventory to see all holdings and reward access.", body),
        Paragraph("Manual move format: one move per line as <b>Name | Description | Damage | Unlock level | Cooldown | Effect</b>. Each category accepts one or more moves, with no fixed three-move ceiling. Villains also receive minimum and maximum player levels; their health and damage scale upward for eligible higher-level players.", body),
        Paragraph("For artwork, upload an image through @vTelegraphBot and provide the resulting https://telegra.ph/ or https://graph.org/ URL. CapeVerse validates the URL and stores it with the content. If Telegram cannot preview the image, the text draft still remains available.", body),
        Paragraph("15 · Approval and rights", heading),
        Paragraph("Draft → preview → submit → owner review → publish. Content marked unverified cannot be approved. Original content should use new names, costumes, symbols, silhouettes, stories, and visual identities. Do not use protected Marvel, DC, X-Men, actor, logo, or exact-costume material without documented rights.", body),
        Paragraph("16 · Owner testing and logs", heading),
        Paragraph("/test runs a deterministic simulation using the first published hero and first available normal enemy or villain. It changes no player balance, reward, battle record, or rating. Important user, content, approval, moderator, test, character, and battle events are sent to the owner and configured audit chat.", body),
        Paragraph("17 · Fair play", heading),
        Paragraph("Do not share account access or attempt to alter callbacks. Battles, currencies, rewards, and ownership are server-controlled. Report broken content to the owner before continuing an affected encounter.", body),
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