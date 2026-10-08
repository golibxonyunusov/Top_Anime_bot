"""
Adminlar tizimi.

- Super adminlar config.SUPER_ADMIN_USERNAMES da username bo'yicha beriladi.
  Ular botga birinchi marta yozganda username -> Telegram ID bog'lanadi va
  shundan keyin faqat ID bo'yicha tekshiriladi (username o'zgarsa ham,
  boshqa odam o'sha username'ni olsa ham xavfsiz).
- Oddiy adminlarni super adminlar (yoki ruxsat berilgan adminlar) bot ichidan
  qo'shadi. Ular `admins` jadvalida (Turso) saqlanadi.
- config.ADMIN_IDS ro'yxati "jonli" yangilanadi, shuning uchun user.py,
  admin.py va middlewares.py dagi `user_id in ADMIN_IDS` tekshiruvlari
  hech qanday o'zgartirishsiz ishlayveradi.
"""
from datetime import datetime

from aiogram import BaseMiddleware

import database as db
from config import ADMIN_IDS, SUPER_ADMIN_USERNAMES

# Environment orqali berilgan ID'lar (bot egasi) — doim super admin
BASE_ADMIN_IDS = list(ADMIN_IDS)

_rows: dict[int, dict] = {}      # user_id -> admin qatori (bog'langanlar)
_pending: dict[str, int] = {}    # username(lower) -> admin qatori id (hali botga kirmaganlar)


def _client():
    return db.get_client()


# ---------------------------------------------------------------
# TEKSHIRUVLAR (sinxron, xotiradagi keshdan)
# ---------------------------------------------------------------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_super(user_id: int) -> bool:
    if user_id in BASE_ADMIN_IDS:
        return True
    row = _rows.get(user_id)
    return bool(row and row.get("is_super"))


def can_add_admins(user_id: int) -> bool:
    if is_super(user_id):
        return True
    row = _rows.get(user_id)
    return bool(row and row.get("can_add"))


def row_label(row: dict) -> str:
    if row.get("username"):
        return f"@{row['username']}"
    return f"ID {row.get('user_id')}"


def label(user_id, username) -> str:
    return f"@{username}" if username else f"ID {user_id}"


def already_admin(user_id, username) -> bool:
    if user_id is not None and is_admin(user_id):
        return True
    if username:
        u = username.lower()
        if u in _pending:
            return True
        for r in _rows.values():
            if (r.get("username") or "").lower() == u:
                return True
    return False


# ---------------------------------------------------------------
# BAZA BILAN ISHLASH
# ---------------------------------------------------------------
async def refresh():
    """Bazadan adminlarni o'qib, keshni va ADMIN_IDS ro'yxatini yangilaydi."""
    rs = await _client().execute("SELECT * FROM admins")
    rows = db._rows_to_dicts(rs)
    _rows.clear()
    _pending.clear()
    for r in rows:
        if r["user_id"] is not None:
            _rows[r["user_id"]] = r
        elif r["username"]:
            _pending[r["username"].lower()] = r["id"]
    ADMIN_IDS[:] = list(dict.fromkeys(BASE_ADMIN_IDS + list(_rows.keys())))


async def find_user_id_by_username(username: str):
    rs = await _client().execute(
        "SELECT user_id FROM users WHERE lower(username) = ? LIMIT 1", [username.lower()]
    )
    return rs.rows[0][0] if rs.rows else None


async def init():
    client = _client()
    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            is_super INTEGER DEFAULT 0,
            can_add INTEGER DEFAULT 0,
            added_by INTEGER,
            added_at TEXT
        )
        """
    )
    for raw in SUPER_ADMIN_USERNAMES:
        uname = raw.lstrip("@").lower()
        uid = await find_user_id_by_username(uname)
        rs = await client.execute(
            "SELECT id FROM admins WHERE lower(username) = ? OR (user_id IS NOT NULL AND user_id = ?)",
            [uname, uid if uid is not None else -1],
        )
        if rs.rows:
            await client.execute(
                "UPDATE admins SET is_super = 1, can_add = 1, username = ?, "
                "user_id = COALESCE(user_id, ?) WHERE id = ?",
                [uname, uid, rs.rows[0][0]],
            )
        else:
            await client.execute(
                "INSERT INTO admins (user_id, username, is_super, can_add, added_by, added_at) "
                "VALUES (?, ?, 1, 1, NULL, ?)",
                [uid, uname, datetime.now().isoformat()],
            )
    await refresh()


async def list_admins() -> list[dict]:
    rs = await _client().execute("SELECT * FROM admins ORDER BY is_super DESC, id ASC")
    return db._rows_to_dicts(rs)


async def get_row(row_id: int):
    rs = await _client().execute("SELECT * FROM admins WHERE id = ?", [row_id])
    rows = db._rows_to_dicts(rs)
    return rows[0] if rows else None


async def add_admin(user_id, username, can_add: bool, added_by: int):
    await _client().execute(
        "INSERT INTO admins (user_id, username, is_super, can_add, added_by, added_at) "
        "VALUES (?, ?, 0, ?, ?, ?)",
        [user_id, username.lower() if username else None, int(can_add), added_by,
         datetime.now().isoformat()],
    )
    await refresh()


async def set_can_add(row_id: int, value: bool):
    await _client().execute(
        "UPDATE admins SET can_add = ? WHERE id = ? AND is_super = 0", [int(value), row_id]
    )
    await refresh()


async def remove_admin(row_id: int):
    await _client().execute("DELETE FROM admins WHERE id = ? AND is_super = 0", [row_id])
    await refresh()


# ---------------------------------------------------------------
# USERNAME -> ID BOG'LASH
# ---------------------------------------------------------------
async def sync_user(user):
    """Username bo'yicha qo'shilgan (hali ID'si noma'lum) admin botga yozsa, ID'sini bog'laydi."""
    uname = (user.username or "").lower()
    if uname and uname in _pending:
        await _client().execute(
            "UPDATE admins SET user_id = ? WHERE id = ? AND user_id IS NULL",
            [user.id, _pending[uname]],
        )
        await refresh()


class AdminSyncMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is not None:
            try:
                await sync_user(user)
            except Exception as e:
                print(f"⚠️ Admin sinxronlashda xato: {e}")
        return await handler(event, data)