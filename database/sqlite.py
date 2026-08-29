import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path(os.getenv("DATABASE_PATH", "data/capeverse.sqlite3"))


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                origin TEXT DEFAULT '',
                passive TEXT DEFAULT '',
                credits INTEGER NOT NULL DEFAULT 500,
                signal_shards INTEGER NOT NULL DEFAULT 2,
                prism_cores INTEGER NOT NULL DEFAULT 0,
                patrol_intel INTEGER NOT NULL DEFAULT 5,
                rating INTEGER NOT NULL DEFAULT 1000,
                rift_floor INTEGER NOT NULL DEFAULT 1,
                guide_sent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS heroes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hero_key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                codename TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'Capeverse Original',
                rights_status TEXT NOT NULL DEFAULT 'approved',
                universe TEXT NOT NULL DEFAULT 'Capeverse Originals',
                faction TEXT NOT NULL DEFAULT 'Independent',
                role TEXT NOT NULL DEFAULT 'Fighter',
                rarity TEXT NOT NULL DEFAULT 'Rare',
                alignment TEXT NOT NULL DEFAULT 'Hero',
                description TEXT NOT NULL DEFAULT '',
                image_url TEXT DEFAULT '',
                ability_signature TEXT DEFAULT '',
                ability_utility TEXT DEFAULT '',
                ability_ultimate TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'published',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS owned_heroes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                hero_id INTEGER NOT NULL REFERENCES heroes(id),
                level INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0,
                stars INTEGER NOT NULL DEFAULT 1,
                evolved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, hero_id)
            );

            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                team_number INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL DEFAULT 'Team 1',
                UNIQUE(user_id, team_number)
            );

            CREATE TABLE IF NOT EXISTS team_members (
                team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                slot INTEGER NOT NULL,
                owned_hero_id INTEGER NOT NULL REFERENCES owned_heroes(id),
                PRIMARY KEY(team_id, slot)
            );

            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                currency TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                balance_after INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                mode TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                turn INTEGER NOT NULL DEFAULT 1,
                player_hp INTEGER NOT NULL DEFAULT 100,
                enemy_hp INTEGER NOT NULL DEFAULT 100,
                log_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS content_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_kind TEXT NOT NULL,
                title TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                submitted_by TEXT NOT NULL,
                reviewed_by TEXT DEFAULT '',
                review_note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                reviewed_at TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS moderators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT DEFAULT '',
                permissions_json TEXT NOT NULL DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS banners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                featured_hero_key TEXT NOT NULL,
                cost_shards INTEGER NOT NULL DEFAULT 1,
                signal_boost INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            );
            """
        )


def get_or_create_user(telegram_id: int, username: str = "", first_name: str = "") -> sqlite3.Row:
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET username = ?, first_name = ?, last_seen_at = ? WHERE telegram_id = ?",
                (username or "", first_name or "", now(), telegram_id),
            )
            return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        conn.execute(
            """
            INSERT INTO users (telegram_id, username, first_name, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (telegram_id, username or "", first_name or "", now(), now()),
        )
        return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()


def get_profile(telegram_id: int) -> sqlite3.Row | None:
    with connection() as conn:
        return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()


def update_player(telegram_id: int, **fields: Any) -> sqlite3.Row | None:
    allowed = {
        "origin",
        "passive",
        "credits",
        "signal_shards",
        "prism_cores",
        "patrol_intel",
        "rating",
        "rift_floor",
        "guide_sent",
    }
    clean = {key: value for key, value in fields.items() if key in allowed}
    if not clean:
        return get_profile(telegram_id)
    assignments = ", ".join(f"{key} = ?" for key in clean)
    values = [clean[key] for key in clean]
    values.append(telegram_id)
    with connection() as conn:
        conn.execute(f"UPDATE users SET {assignments}, last_seen_at = ? WHERE telegram_id = ?", (*values[:-1], now(), values[-1]))
        return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()


def list_heroes(status: str = "published") -> list[sqlite3.Row]:
    with connection() as conn:
        if status == "all":
            return conn.execute("SELECT * FROM heroes ORDER BY rarity DESC, name").fetchall()
        return conn.execute("SELECT * FROM heroes WHERE status = ? ORDER BY rarity DESC, name", (status,)).fetchall()


def get_hero(hero_key: str) -> sqlite3.Row | None:
    with connection() as conn:
        return conn.execute("SELECT * FROM heroes WHERE hero_key = ?", (hero_key,)).fetchone()


def list_owned_heroes(telegram_id: int) -> list[sqlite3.Row]:
    with connection() as conn:
        return conn.execute(
            """
            SELECT oh.*, h.hero_key, h.name, h.codename, h.role, h.rarity, h.universe, h.alignment
            FROM owned_heroes oh
            JOIN users u ON u.id = oh.user_id
            JOIN heroes h ON h.id = oh.hero_id
            WHERE u.telegram_id = ?
            ORDER BY oh.stars DESC, oh.level DESC, h.name
            """,
            (telegram_id,),
        ).fetchall()


def add_hero_to_player(telegram_id: int, hero_key: str) -> sqlite3.Row | None:
    with connection() as conn:
        hero = conn.execute("SELECT * FROM heroes WHERE hero_key = ?", (hero_key,)).fetchone()
        user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if not hero or not user:
            return None
        owned = conn.execute(
            "SELECT * FROM owned_heroes WHERE user_id = ? AND hero_id = ?",
            (user["id"], hero["id"]),
        ).fetchone()
        if owned:
            conn.execute("UPDATE owned_heroes SET stars = stars + 1 WHERE id = ?", (owned["id"],))
        else:
            conn.execute(
                """
                INSERT INTO owned_heroes (user_id, hero_id, created_at)
                VALUES (?, ?, ?)
                """,
                (user["id"], hero["id"], now()),
            )
        return conn.execute(
            """
            SELECT oh.*, h.name, h.codename, h.role, h.rarity, h.universe
            FROM owned_heroes oh JOIN heroes h ON h.id = oh.hero_id
            WHERE oh.user_id = ? AND oh.hero_id = ?
            """,
            (user["id"], hero["id"]),
        ).fetchone()


def save_team(telegram_id: int, owned_ids: list[int], team_number: int = 1) -> None:
    with connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if not user:
            return
        team = conn.execute(
            "SELECT * FROM teams WHERE user_id = ? AND team_number = ?",
            (user["id"], team_number),
        ).fetchone()
        if not team:
            conn.execute(
                "INSERT INTO teams (user_id, team_number, name) VALUES (?, ?, ?)",
                (user["id"], team_number, f"Team {team_number}"),
            )
            team = conn.execute(
                "SELECT * FROM teams WHERE user_id = ? AND team_number = ?",
                (user["id"], team_number),
            ).fetchone()
        conn.execute("DELETE FROM team_members WHERE team_id = ?", (team["id"],))
        for slot, owned_id in enumerate(owned_ids[:3], 1):
            conn.execute(
                "INSERT OR IGNORE INTO team_members (team_id, slot, owned_hero_id) VALUES (?, ?, ?)",
                (team["id"], slot, owned_id),
            )


def get_team(telegram_id: int, team_number: int = 1) -> list[sqlite3.Row]:
    with connection() as conn:
        return conn.execute(
            """
            SELECT tm.slot, oh.*, h.name, h.codename, h.role, h.rarity, h.universe
            FROM teams t
            JOIN users u ON u.id = t.user_id
            JOIN team_members tm ON tm.team_id = t.id
            JOIN owned_heroes oh ON oh.id = tm.owned_hero_id
            JOIN heroes h ON h.id = oh.hero_id
            WHERE u.telegram_id = ? AND t.team_number = ?
            ORDER BY tm.slot
            """,
            (telegram_id, team_number),
        ).fetchall()


def record_ledger(telegram_id: int, currency: str, amount: int, reason: str, balance_after: int) -> None:
    with connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if user:
            conn.execute(
                """
                INSERT INTO ledger (user_id, currency, amount, reason, balance_after, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user["id"], currency, amount, reason, balance_after, now()),
            )


def create_battle(telegram_id: int, mode: str, stage: str, enemy_hp: int = 100) -> int:
    with connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if not user:
            raise ValueError("Player does not exist")
        cursor = conn.execute(
            """
            INSERT INTO battles (user_id, mode, stage, player_hp, enemy_hp, created_at, updated_at)
            VALUES (?, ?, ?, 100, ?, ?, ?)
            """,
            (user["id"], mode, stage, enemy_hp, now(), now()),
        )
        return int(cursor.lastrowid)


def get_battle(telegram_id: int, battle_id: int) -> sqlite3.Row | None:
    with connection() as conn:
        return conn.execute(
            """
            SELECT b.* FROM battles b JOIN users u ON u.id = b.user_id
            WHERE u.telegram_id = ? AND b.id = ?
            """,
            (telegram_id, battle_id),
        ).fetchone()


def update_battle(battle_id: int, **fields: Any) -> sqlite3.Row | None:
    allowed = {"status", "turn", "player_hp", "enemy_hp", "log_json"}
    clean = {key: value for key, value in fields.items() if key in allowed}
    if not clean:
        return None
    assignments = ", ".join(f"{key} = ?" for key in clean)
    values = [clean[key] for key in clean]
    values.extend([now(), battle_id])
    with connection() as conn:
        conn.execute(f"UPDATE battles SET {assignments}, updated_at = ? WHERE id = ?", values)
        return conn.execute("SELECT * FROM battles WHERE id = ?", (battle_id,)).fetchone()


def seed_hero(data: dict[str, Any]) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO heroes
            (hero_key, name, codename, source, rights_status, universe, faction, role,
             rarity, alignment, description, ability_signature, ability_utility, ability_ultimate, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["hero_key"],
                data["name"],
                data["codename"],
                data.get("source", "Capeverse Original"),
                data.get("rights_status", "approved"),
                data.get("universe", "Capeverse Originals"),
                data.get("faction", "Independent"),
                data.get("role", "Fighter"),
                data.get("rarity", "Rare"),
                data.get("alignment", "Hero"),
                data.get("description", ""),
                data.get("ability_signature", ""),
                data.get("ability_utility", ""),
                data.get("ability_ultimate", ""),
                data.get("status", "published"),
                now(),
            ),
        )


def add_submission(kind: str, title: str, payload: dict[str, Any], submitted_by: str) -> int:
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO content_submissions
            (content_kind, title, payload_json, submitted_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (kind, title, json.dumps(payload), submitted_by, now()),
        )
        return int(cursor.lastrowid)


def list_submissions(status: str = "pending") -> list[sqlite3.Row]:
    with connection() as conn:
        return conn.execute(
            "SELECT * FROM content_submissions WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()


def review_submission(submission_id: int, status: str, reviewer: str, note: str = "") -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE content_submissions
            SET status = ?, reviewed_by = ?, review_note = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (status, reviewer, note, now(), submission_id),
        )


def upsert_moderator(telegram_id: int, username: str, permissions: list[str]) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO moderators (telegram_id, username, permissions_json, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
              username = excluded.username,
              permissions_json = excluded.permissions_json,
              active = 1
            """,
            (telegram_id, username, json.dumps(permissions), now()),
        )


def list_moderators() -> list[sqlite3.Row]:
    with connection() as conn:
        return conn.execute("SELECT * FROM moderators WHERE active = 1 ORDER BY created_at DESC").fetchall()