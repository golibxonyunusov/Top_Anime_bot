import math
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


# ---------------------------------------------------------------
# CALLBACK DATA SXEMALARI
# ---------------------------------------------------------------
class AnimeCB(CallbackData, prefix="anime"):
    id: int
    action: str  # view | fav | unfav | episodes


class EpisodeCB(CallbackData, prefix="ep"):
    anime_id: int
    ep_id: int


class PageCB(CallbackData, prefix="page"):
    scope: str  # all | fav | search | episodes
    anime_id: int  # faqat episodes uchun kerak, aks holda 0
    page: int


class AdminAnimeCB(CallbackData, prefix="a_anime"):
    id: int
    action: str  # edit | delete | confirm_delete | add_ep


class EditFieldCB(CallbackData, prefix="editf"):
    id: int
    field: str


class ConfirmCB(CallbackData, prefix="confirm"):
    action: str
    id: int


class ChannelCB(CallbackData, prefix="channel"):
    id: int
    action: str  # delete


# ---------------------------------------------------------------
# REPLY (pastki) MENYULAR
# ---------------------------------------------------------------
def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🔎 Qidirish"), KeyboardButton(text="📋 Barcha animelar"))
    b.row(KeyboardButton(text="⭐ Sevimlilar"), KeyboardButton(text="ℹ️ Yordam"))
    if is_admin:
        b.row(KeyboardButton(text="🛠 Admin panel"))
    return b.as_markup(resize_keyboard=True)


def admin_menu_kb() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="➕ Anime qo'shish"), KeyboardButton(text="🎬 Qism qo'shish"))
    b.row(KeyboardButton(text="✏️ Tahrirlash"), KeyboardButton(text="🗑 Anime o'chirish"))
    b.row(KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Xabar yuborish"))
    b.row(KeyboardButton(text="🔐 Majburiy obuna"), KeyboardButton(text="👥 Adminlar"))
    b.row(KeyboardButton(text="⬅️ Bosh menyu"))
    return b.as_markup(resize_keyboard=True)


def obuna_menu_kb() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="➕ Kanal qo'shish"))
    b.row(KeyboardButton(text="📋 Kanallar ro'yxati"))
    b.row(KeyboardButton(text="⬅️ Admin panel"))
    return b.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="❌ Bekor qilish"))
    return b.as_markup(resize_keyboard=True)


def skip_cancel_kb() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="⏭ O'tkazib yuborish"), KeyboardButton(text="❌ Bekor qilish"))
    return b.as_markup(resize_keyboard=True)


def finish_cancel_kb() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="✅ Yakunlash"), KeyboardButton(text="❌ Bekor qilish"))
    return b.as_markup(resize_keyboard=True)


# ---------------------------------------------------------------
# INLINE — ANIME KARTASI
# ---------------------------------------------------------------
def anime_card_kb(anime_id: int, is_fav: bool, has_episodes: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_episodes:
        b.button(text="🎬 Qismlarni ko'rish", callback_data=AnimeCB(id=anime_id, action="episodes"))
    if is_fav:
        b.button(text="❌ Sevimlidan olib tashlash", callback_data=AnimeCB(id=anime_id, action="unfav"))
    else:
        b.button(text="⭐ Sevimlilarga qo'shish", callback_data=AnimeCB(id=anime_id, action="fav"))
    b.adjust(1)
    return b.as_markup()


def episodes_kb(anime_id: int, episodes, page: int, per_page: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = page * per_page
    chunk = episodes[start:start + per_page]
    for ep in chunk:
        b.button(text=f"{ep['episode_number']}-qism", callback_data=EpisodeCB(anime_id=anime_id, ep_id=ep["id"]))

    total_pages = max(1, math.ceil(len(episodes) / per_page))
    if total_pages > 1:
        if page > 0:
            b.button(text="⬅️", callback_data=PageCB(scope="episodes", anime_id=anime_id, page=page - 1))
        b.button(text=f"📄 {page + 1}/{total_pages}", callback_data="noop")
        if page < total_pages - 1:
            b.button(text="➡️", callback_data=PageCB(scope="episodes", anime_id=anime_id, page=page + 1))

    b.button(text="🔙 Anime sahifasiga qaytish", callback_data=AnimeCB(id=anime_id, action="view"))

    rows = [4] * math.ceil(len(chunk) / 4) if chunk else []
    if total_pages > 1:
        nav_count = (1 if page > 0 else 0) + 1 + (1 if page < total_pages - 1 else 0)
        rows.append(nav_count)
    rows.append(1)
    b.adjust(*rows)
    return b.as_markup()


def anime_list_kb(anime_rows, scope: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for a in anime_rows:
        b.button(text=f"#{a['id']} — {a['title']}", callback_data=AnimeCB(id=a["id"], action="view"))
    b.adjust(1)

    if total_pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=PageCB(scope=scope, anime_id=0, page=page - 1))
        nav.button(text=f"📄 {page + 1}/{total_pages}", callback_data="noop")
        if page < total_pages - 1:
            nav.button(text="➡️", callback_data=PageCB(scope=scope, anime_id=0, page=page + 1))
        nav.adjust(3)
        b.attach(nav)
    return b.as_markup()


def back_to_anime_kb(anime_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 Anime sahifasiga qaytish", callback_data=AnimeCB(id=anime_id, action="view"))
    return b.as_markup()


# ---------------------------------------------------------------
# INLINE — ADMIN
# ---------------------------------------------------------------
def edit_fields_kb(anime_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    fields = [
        ("📝 Nomi", "title"),
        ("📖 Tavsif", "description"),
        ("🏷 Janr", "genre"),
        ("📅 Yil", "year"),
        ("📌 Holati", "status"),
        ("🖼 Poster", "poster"),
    ]
    for label, field in fields:
        b.button(text=label, callback_data=EditFieldCB(id=anime_id, field=field))
    b.adjust(2)
    return b.as_markup()


def confirm_delete_kb(anime_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data=ConfirmCB(action="delete_anime", id=anime_id))
    b.button(text="❌ Bekor qilish", callback_data=ConfirmCB(action="cancel", id=anime_id))
    b.adjust(2)
    return b.as_markup()


def status_choice_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🟢 Davom etmoqda", callback_data="status_Davom etmoqda")
    b.button(text="✅ Nihoyasiga yetgan", callback_data="status_Nihoyasiga yetgan")
    b.adjust(1)
    return b.as_markup()


def channels_list_kb(channels) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.button(text=f"❌ {ch['title']}", callback_data=ChannelCB(id=ch["id"], action="delete"))
    b.adjust(1)
    return b.as_markup()


def force_sub_kb(channels) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.button(text=f"➕ {ch['title']}", url=ch["invite_link"])
    b.button(text="✅ A'zo bo'ldim", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()