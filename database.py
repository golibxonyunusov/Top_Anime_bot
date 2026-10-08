import os
from datetime import datetime

import libsql_client

from config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN

ALLOWED_EDIT_FIELDS = {"title", "description", "genre", "year", "status", "poster"}

_client = None


def get_client() -> libsql_client.Client:
    """Turso (libSQL) bilan ulanishni bir marta yaratib, qayta ishlatadi."""
    global _client
    if _client is None:
        if not TURSO_DATABASE_URL:
            raise RuntimeError(
                "TURSO_DATABASE_URL topilmadi! config.py yoki Render Environment "
                "Variables orqali kiriting."
            )
        _client = libsql_client.create_client(
            url=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN or None
        )
    return _client


def _rows_to_dicts(rs) -> list[dict]:
    return [dict(zip(rs.columns, row)) for row in rs.rows]


async def init_db():
    client = get_client()
    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            genre TEXT DEFAULT '',
            year INTEGER,
            status TEXT DEFAULT 'Davom etmoqda',
            poster TEXT,
            views INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )
    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER NOT NULL,
            episode_number INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            added_at TEXT
        )
        """
    )
    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_at TEXT,
            is_banned INTEGER DEFAULT 0
        )
        """
    )
    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            anime_id INTEGER,
            PRIMARY KEY (user_id, anime_id)
        )
        """
    )
    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            title TEXT NOT NULL,
            invite_link TEXT NOT NULL,
            added_at TEXT
        )
        """
    )


# ---------------------------------------------------------------
# USERS
# ---------------------------------------------------------------
async def add_user(user_id: int, username: str, full_name: str):
    client = get_client()
    await client.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at) VALUES (?, ?, ?, ?)",
        [user_id, username or "", full_name or "", datetime.now().isoformat()],
    )


async def get_user_count() -> int:
    client = get_client()
    rs = await client.execute("SELECT COUNT(*) FROM users")
    return rs.rows[0][0]


async def get_all_user_ids() -> list[int]:
    client = get_client()
    rs = await client.execute("SELECT user_id FROM users WHERE is_banned = 0")
    return [row[0] for row in rs.rows]


# ---------------------------------------------------------------
# ANIME
# ---------------------------------------------------------------
async def add_anime(title, description, genre, year, status, poster) -> int:
    client = get_client()
    rss = await client.batch(
        [
            libsql_client.Statement(
                """INSERT INTO anime (title, description, genre, year, status, poster, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [title, description, genre, year, status, poster, datetime.now().isoformat()],
            ),
            "SELECT last_insert_rowid()",
        ]
    )
    return rss[1].rows[0][0]


async def get_anime_by_id(anime_id: int):
    client = get_client()
    rs = await client.execute("SELECT * FROM anime WHERE id = ?", [anime_id])
    rows = _rows_to_dicts(rs)
    return rows[0] if rows else None


async def search_anime_by_name(query: str, limit: int = 20):
    client = get_client()
    rs = await client.execute(
        "SELECT * FROM anime WHERE title LIKE ? ORDER BY id DESC LIMIT ?",
        [f"%{query}%", limit],
    )
    return _rows_to_dicts(rs)


async def get_all_anime(page: int, per_page: int):
    client = get_client()
    offset = page * per_page
    rs = await client.execute(
        "SELECT * FROM anime ORDER BY id DESC LIMIT ? OFFSET ?", [per_page, offset]
    )
    return _rows_to_dicts(rs)


async def count_anime() -> int:
    client = get_client()
    rs = await client.execute("SELECT COUNT(*) FROM anime")
    return rs.rows[0][0]


async def delete_anime(anime_id: int):
    client = get_client()
    await client.batch(
        [
            libsql_client.Statement("DELETE FROM anime WHERE id = ?", [anime_id]),
            libsql_client.Statement("DELETE FROM episodes WHERE anime_id = ?", [anime_id]),
            libsql_client.Statement("DELETE FROM favorites WHERE anime_id = ?", [anime_id]),
        ]
    )


async def update_anime_field(anime_id: int, field: str, value):
    if field not in ALLOWED_EDIT_FIELDS:
        raise ValueError("Ruxsat etilmagan maydon")
    client = get_client()
    await client.execute(f"UPDATE anime SET {field} = ? WHERE id = ?", [value, anime_id])


async def increment_views(anime_id: int):
    client = get_client()
    await client.execute("UPDATE anime SET views = views + 1 WHERE id = ?", [anime_id])


async def get_top_anime(limit: int = 5):
    client = get_client()
    rs = await client.execute("SELECT * FROM anime ORDER BY views DESC LIMIT ?", [limit])
    return _rows_to_dicts(rs)


# ---------------------------------------------------------------
# EPISODES
# ---------------------------------------------------------------
async def add_episode(anime_id: int, episode_number: int, file_id: str) -> int:
    client = get_client()
    rss = await client.batch(
        [
            libsql_client.Statement(
                """INSERT INTO episodes (anime_id, episode_number, file_id, added_at)
                   VALUES (?, ?, ?, ?)""",
                [anime_id, episode_number, file_id, datetime.now().isoformat()],
            ),
            "SELECT last_insert_rowid()",
        ]
    )
    return rss[1].rows[0][0]


async def get_episodes(anime_id: int):
    client = get_client()
    rs = await client.execute(
        "SELECT * FROM episodes WHERE anime_id = ? ORDER BY episode_number ASC", [anime_id]
    )
    return _rows_to_dicts(rs)


async def get_episode(episode_id: int):
    client = get_client()
    rs = await client.execute("SELECT * FROM episodes WHERE id = ?", [episode_id])
    rows = _rows_to_dicts(rs)
    return rows[0] if rows else None


async def count_episodes() -> int:
    client = get_client()
    rs = await client.execute("SELECT COUNT(*) FROM episodes")
    return rs.rows[0][0]


async def delete_episode(episode_id: int):
    client = get_client()
    await client.execute("DELETE FROM episodes WHERE id = ?", [episode_id])


# ---------------------------------------------------------------
# FAVORITES
# ---------------------------------------------------------------
async def add_favorite(user_id: int, anime_id: int):
    client = get_client()
    await client.execute(
        "INSERT OR IGNORE INTO favorites (user_id, anime_id) VALUES (?, ?)",
        [user_id, anime_id],
    )


async def remove_favorite(user_id: int, anime_id: int):
    client = get_client()
    await client.execute(
        "DELETE FROM favorites WHERE user_id = ? AND anime_id = ?", [user_id, anime_id]
    )


async def is_favorite(user_id: int, anime_id: int) -> bool:
    client = get_client()
    rs = await client.execute(
        "SELECT 1 FROM favorites WHERE user_id = ? AND anime_id = ?", [user_id, anime_id]
    )
    return len(rs.rows) > 0


async def get_favorites(user_id: int):
    client = get_client()
    rs = await client.execute(
        """SELECT anime.* FROM anime
           JOIN favorites ON anime.id = favorites.anime_id
           WHERE favorites.user_id = ? ORDER BY anime.id DESC""",
        [user_id],
    )
    return _rows_to_dicts(rs)


# ---------------------------------------------------------------
# MAJBURIY OBUNA KANALLARI
# ---------------------------------------------------------------
async def add_channel(channel_id: str, title: str, invite_link: str):
    client = get_client()
    await client.execute(
        "INSERT INTO channels (channel_id, title, invite_link, added_at) VALUES (?, ?, ?, ?)",
        [channel_id, title, invite_link, datetime.now().isoformat()],
    )


async def get_all_channels():
    client = get_client()
    rs = await client.execute("SELECT * FROM channels ORDER BY id ASC")
    return _rows_to_dicts(rs)


async def delete_channel(channel_row_id: int):
    client = get_client()
    await client.execute("DELETE FROM channels WHERE id = ?", [channel_row_id])


async def count_channels() -> int:
    client = get_client()
    rs = await client.execute("SELECT COUNT(*) FROM channels")
    return rs.rows[0][0]