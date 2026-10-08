# ============================================================
#  Top_Anime Bot — Konfiguratsiya
# ============================================================
# Maxfiy qiymatlar (token va h.k.) bu faylda YOZILMAYDI.
# Ular .env fayldan (lokal) yoki Render "Environment" bo'limidan
# (serverda) o'qiladi:
#   BOT_TOKEN, ADMIN_IDS, SUPER_ADMIN_USERNAMES, ANIME_CHANNEL,
#   TURSO_DATABASE_URL, TURSO_AUTH_TOKEN
# ============================================================

import os

# Lokal ishlatishda .env faylni o'qiydi (python-dotenv o'rnatilgan bo'lsa).
# Render'da bu kerak emas, u yerda o'zgaruvchilar to'g'ridan-to'g'ri keladi.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# bot.py shu qiymatni tekshiradi, shuning uchun o'zgartirmang
BOT_TOKEN = os.environ.get("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")

ANIME_CHANNEL = os.environ.get("ANIME_CHANNEL", "@animelartopuz")

# ADMIN_IDS: masalan "123456789,987654321". Bular "bot egasi" — doim super admin.
_admin_ids_raw = os.environ.get("ADMIN_IDS", "8888728779")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip()]

# Super adminlar username bo'yicha (@belgisiz), vergul bilan ajratiladi.
_super_raw = os.environ.get("SUPER_ADMIN_USERNAMES", "")
SUPER_ADMIN_USERNAMES = [x.strip().lstrip("@") for x in _super_raw.split(",") if x.strip()]

# ---------------------------------------------------------------
# Turso (libSQL). libsql:// manzili WebSocket (wss://) orqali ulanib,
# 400 xatosini beradi, shuning uchun avtomatik https:// ga o'giramiz.
#
# Lokal sinov uchun TURSO_DATABASE_URL ni "file:uzumdub.db" qilsa
# bo'ladi (Render'da BUNI QILMANG).
# ---------------------------------------------------------------
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "file:uzumdub.db").replace(
    "libsql://", "https://"
)
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

STUDIO_NAME = "Top_Anime"

# Bosh menyudagi banner matni (ixtiyoriy, /start da chiqadi)
WELCOME_TEXT = (
    "<b>{studio}</b> botimizga ga xush kelibsiz!\n\n"
    "Bu yerda siz sevimli animelaringizni o'zbek tilidagi dublyajda "
    "topishingiz mumkin.\n\n"
    "🔎 Anime nomi yoki <b>ID</b> raqami orqali qidiring\n"
    "📋 Barcha animelar ro'yxatini ko'ring\n"
    "⭐ Sevimlilarga qo'shib qo'ying\n\n"
    "Quyidagi tugmalardan birini tanlang 👇"
)

# Har bir sahifada nechta anime/qism ko'rsatilsin
ANIME_PER_PAGE = 6
EPISODES_PER_PAGE = 12