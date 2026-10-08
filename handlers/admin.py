import asyncio
import html
import re

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

import database as db
import keyboards as kb
import permissions as perm
from config import ANIME_CHANNEL

router = Router()

USERNAME_RE = re.compile(r"@?([A-Za-z][A-Za-z0-9_]{3,31})")

SKIP = "⏭ O'tkazib yuborish"
CANCEL = "❌ Bekor qilish"
FINISH = "✅ Yakunlash"


# Bu router faqat adminlar uchun: admin bo'lmaganlarning xabarlari
# to'g'ridan-to'g'ri user routeriga o'tib ketadi.
async def _is_admin_event(event) -> bool:
    user = getattr(event, "from_user", None)
    return user is not None and perm.is_admin(user.id)


router.message.filter(_is_admin_event)
router.callback_query.filter(_is_admin_event)


# ---------------------------------------------------------------
# HOLATLAR VA CALLBACK'LAR
# ---------------------------------------------------------------
class AddAdmin(StatesGroup):
    target = State()
    permission = State()


class AddAnime(StatesGroup):
    title = State()
    description = State()
    genre = State()
    year = State()
    status = State()
    poster = State()


class AddEpisode(StatesGroup):
    anime_id = State()
    number = State()
    video = State()


class EditAnime(StatesGroup):
    anime_id = State()
    value = State()


class DeleteAnime(StatesGroup):
    anime_id = State()


class Broadcast(StatesGroup):
    content = State()


class AddChannel(StatesGroup):
    target = State()


class NewAdminCB(CallbackData, prefix="newadm"):
    can_add: int  # 0 | 1


class AdmCB(CallbackData, prefix="adm"):
    id: int
    action: str  # list | open | toggle | ask_del | del


# ---------------------------------------------------------------
# TUGMALAR
# ---------------------------------------------------------------
def admins_menu_kb() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="➕ Admin qo'shish"))
    b.row(KeyboardButton(text="📋 Adminlar ro'yxati"))
    b.row(KeyboardButton(text="⬅️ Admin panel"))
    return b.as_markup(resize_keyboard=True)


def permission_choice_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 Oddiy admin", callback_data=NewAdminCB(can_add=0))
    b.button(text="🔑 Admin + yangi admin qo'sha oladi", callback_data=NewAdminCB(can_add=1))
    b.adjust(1)
    return b.as_markup()


def _role_text(row: dict) -> str:
    if row.get("is_super"):
        return "👑 super admin"
    if row.get("can_add"):
        return "🔑 admin + admin qo'sha oladi"
    return "👤 admin"


def _pending_note(row: dict) -> str:
    return " <i>(hali botga kirmagan)</i>" if row.get("user_id") is None else ""


async def render_list(viewer_id: int):
    rows = await perm.list_admins()
    lines = [f"👥 <b>Adminlar</b> ({len(rows)} ta):\n"]
    for r in rows:
        lines.append(f"• {perm.row_label(r)} — {_role_text(r)}{_pending_note(r)}")
    for uid in perm.BASE_ADMIN_IDS:
        lines.append(f"• ID {uid} — 👑 bot egasi")

    markup = None
    if perm.is_super(viewer_id):
        b = InlineKeyboardBuilder()
        for r in rows:
            if not r["is_super"]:
                b.button(text=f"⚙️ {perm.row_label(r)}", callback_data=AdmCB(id=r["id"], action="open"))
        b.adjust(1)
        if rows and any(not r["is_super"] for r in rows):
            lines.append("\nBoshqarish uchun adminni tanlang 👇")
            markup = b.as_markup()
    return "\n".join(lines), markup


def detail_view(row: dict):
    can_add = bool(row.get("can_add"))
    text = (
        f"⚙️ <b>{perm.row_label(row)}</b>\n"
        f"Holati: {_role_text(row)}{_pending_note(row)}"
    )
    b = InlineKeyboardBuilder()
    b.button(
        text=("🔒 Admin qo'shish ruxsatini olib tashlash" if can_add
              else "🔑 Admin qo'shish ruxsatini berish"),
        callback_data=AdmCB(id=row["id"], action="toggle"),
    )
    b.button(text="🗑 Adminlikdan olish", callback_data=AdmCB(id=row["id"], action="ask_del"))
    b.button(text="🔙 Ro'yxatga qaytish", callback_data=AdmCB(id=0, action="list"))
    b.adjust(1)
    return text, b.as_markup()


async def _edit(cb: CallbackQuery, text: str, markup):
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass


# ---------------------------------------------------------------
# 🛠 ADMIN PANEL
# ---------------------------------------------------------------
@router.message(Command("admin"))
@router.message(F.text.in_({"🛠 Admin panel", "⬅️ Admin panel"}))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=kb.admin_menu_kb())


# Barcha admin jarayonlari uchun umumiy "Bekor qilish"
@router.message(
    StateFilter(AddAnime, AddEpisode, EditAnime, DeleteAnime, Broadcast, AddChannel),
    F.text == CANCEL,
)
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=kb.admin_menu_kb())


# ---------------------------------------------------------------
# 📢 KANALGA AVTO-POST
# ---------------------------------------------------------------
async def post_anime_to_channel(bot: Bot, anime_id: int, data: dict, poster):
    """Yangi qo'shilgan animeni kanalga joylaydi.
    Muvaffaqiyatli bo'lsa None, xato bo'lsa xato matnini qaytaradi."""
    try:
        lines = [f"🎬 <b>{html.escape(data['title'])}</b>", ""]
        if data.get("genre"):
            lines.append(f"🏷 Janr: {html.escape(data['genre'])}")
        if data.get("year"):
            lines.append(f"📅 Yil: {data['year']}")
        lines.append(f"📌 Holati: {html.escape(data.get('status', 'Davom etmoqda'))}")
        lines.append(f"🆔 ID: <code>{anime_id}</code>")
        desc = (data.get("description") or "").strip()
        if desc:
            if len(desc) > 450:
                desc = desc[:450].rstrip() + "..."
            lines.append(f"\n📖 {html.escape(desc)}")
        lines.append("\n🔎 Botga kirib nomi yoki ID raqami orqali toping 👇")
        caption = "\n".join(lines)[:1024]

        me = await bot.get_me()
        b = InlineKeyboardBuilder()
        b.button(text="▶️ Botda ko'rish", url=f"https://t.me/{me.username}?start=anime_{anime_id}")
        markup = b.as_markup()

        if poster:
            await bot.send_photo(ANIME_CHANNEL, poster, caption=caption, reply_markup=markup)
        else:
            await bot.send_message(ANIME_CHANNEL, caption, reply_markup=markup)
        return None
    except Exception as e:
        return str(e)


# ---------------------------------------------------------------
# ➕ ANIME QO'SHISH
# ---------------------------------------------------------------
@router.message(F.text == "➕ Anime qo'shish")
async def anime_add_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AddAnime.title)
    await message.answer("📝 Anime <b>nomini</b> yuboring:", reply_markup=kb.cancel_kb())


@router.message(AddAnime.title)
async def anime_add_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("❗️ Iltimos, nomni matn ko'rinishida yuboring.")
        return
    await state.update_data(title=title)
    await state.set_state(AddAnime.description)
    await message.answer("📖 Anime <b>tavsifini</b> yuboring:", reply_markup=kb.skip_cancel_kb())


@router.message(AddAnime.description)
async def anime_add_description(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t:
        await message.answer("❗️ Matn yuboring yoki o'tkazib yuboring.")
        return
    await state.update_data(description="" if t == SKIP else t)
    await state.set_state(AddAnime.genre)
    await message.answer("🏷 <b>Janrini</b> yuboring (masalan: Jangari, Fantastika):", reply_markup=kb.skip_cancel_kb())


@router.message(AddAnime.genre)
async def anime_add_genre(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t:
        await message.answer("❗️ Matn yuboring yoki o'tkazib yuboring.")
        return
    await state.update_data(genre="" if t == SKIP else t)
    await state.set_state(AddAnime.year)
    await message.answer("📅 Chiqqan <b>yilini</b> yuboring (masalan: 2023):", reply_markup=kb.skip_cancel_kb())


@router.message(AddAnime.year)
async def anime_add_year(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if t == SKIP:
        year = None
    elif t.isdigit() and 1900 <= int(t) <= 2100:
        year = int(t)
    else:
        await message.answer("❗️ Yilni raqam bilan yuboring (masalan: 2023) yoki o'tkazib yuboring.")
        return
    await state.update_data(year=year)
    await state.set_state(AddAnime.status)
    await message.answer("📌 Anime <b>holatini</b> tanlang:", reply_markup=kb.status_choice_kb())


@router.message(AddAnime.status)
async def anime_add_status_reminder(message: Message):
    await message.answer("Yuqoridagi tugmalardan birini tanlang yoki ❌ Bekor qilish tugmasini bosing.")


@router.callback_query(AddAnime.status, F.data.startswith("status_"))
async def anime_add_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.removeprefix("status_")
    await state.update_data(status=status)
    await state.set_state(AddAnime.poster)
    await _edit(callback, f"📌 Holati: <b>{html.escape(status)}</b>", None)
    await callback.message.answer(
        "🖼 Anime <b>posterini</b> (rasm) yuboring:", reply_markup=kb.skip_cancel_kb()
    )
    await callback.answer()


@router.message(AddAnime.poster)
async def anime_add_poster(message: Message, state: FSMContext, bot: Bot):
    if message.photo:
        poster = message.photo[-1].file_id
    elif message.text == SKIP:
        poster = None
    else:
        await message.answer("❗️ Rasm yuboring yoki o'tkazib yuboring.")
        return

    data = await state.get_data()
    await state.clear()
    anime_id = await db.add_anime(
        data["title"], data.get("description", ""), data.get("genre", ""),
        data.get("year"), data.get("status", "Davom etmoqda"), poster,
    )
    err = await post_anime_to_channel(bot, anime_id, data, poster)
    channel_note = (
        f"📢 Kanalga ({ANIME_CHANNEL}) joylandi ✅" if err is None
        else f"⚠️ Kanalga joylab bo'lmadi: {html.escape(err)}"
    )
    await message.answer(
        f"✅ Anime qo'shildi!\n\n"
        f"🎬 <b>{html.escape(data['title'])}</b>\n"
        f"🆔 ID: <code>{anime_id}</code>\n"
        f"{channel_note}\n\n"
        f"Qism qo'shish uchun «🎬 Qism qo'shish» tugmasini bosing va shu ID ni kiriting.",
        reply_markup=kb.admin_menu_kb(),
    )


# ---------------------------------------------------------------
# 🎬 QISM QO'SHISH
# ---------------------------------------------------------------
async def _next_ep_number(anime_id: int) -> int:
    eps = await db.get_episodes(anime_id)
    return max((e["episode_number"] for e in eps), default=0) + 1


@router.message(F.text == "🎬 Qism qo'shish")
async def ep_add_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AddEpisode.anime_id)
    await message.answer("🆔 Qism qo'shmoqchi bo'lgan animening <b>ID</b> raqamini yuboring:", reply_markup=kb.cancel_kb())


@router.message(StateFilter(AddEpisode), F.text == FINISH)
async def ep_add_finish(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Qism qo'shish yakunlandi.", reply_markup=kb.admin_menu_kb())


@router.message(AddEpisode.anime_id)
async def ep_add_anime(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    anime = await db.get_anime_by_id(int(t)) if t.isdigit() else None
    if not anime:
        await message.answer("❗️ Bunday ID li anime topilmadi. Qaytadan yuboring.", reply_markup=kb.cancel_kb())
        return
    await state.update_data(anime_id=anime["id"], title=anime["title"])
    await state.set_state(AddEpisode.number)
    nxt = await _next_ep_number(anime["id"])
    await message.answer(
        f"🎬 <b>{html.escape(anime['title'])}</b>\n\n"
        f"Qism <b>raqamini</b> yuboring (keyingisi: <b>{nxt}</b>):",
        reply_markup=kb.finish_cancel_kb(),
    )


@router.message(AddEpisode.number)
async def ep_add_number(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t.isdigit() or int(t) < 1:
        await message.answer("❗️ Qism raqamini butun son bilan yuboring (masalan: 1).")
        return
    data = await state.get_data()
    eps = await db.get_episodes(data["anime_id"])
    if any(e["episode_number"] == int(t) for e in eps):
        await message.answer(f"❗️ {t}-qism allaqachon mavjud. Boshqa raqam yuboring.")
        return
    await state.update_data(ep_number=int(t))
    await state.set_state(AddEpisode.video)
    await message.answer(f"📹 <b>{t}-qism</b> videosini yuboring (fayl emas, video sifatida):")


@router.message(AddEpisode.video)
async def ep_add_video(message: Message, state: FSMContext):
    if not message.video:
        await message.answer("❗️ Iltimos, video yuboring (hujjat/fayl sifatida emas).")
        return
    data = await state.get_data()
    await db.add_episode(data["anime_id"], data["ep_number"], message.video.file_id)
    await state.set_state(AddEpisode.number)
    nxt = await _next_ep_number(data["anime_id"])
    await message.answer(
        f"✅ <b>{data['ep_number']}-qism</b> qo'shildi.\n\n"
        f"Keyingi qism raqamini yuboring (keyingisi: <b>{nxt}</b>) yoki «{FINISH}» tugmasini bosing.",
        reply_markup=kb.finish_cancel_kb(),
    )


# ---------------------------------------------------------------
# ✏️ TAHRIRLASH
# ---------------------------------------------------------------
EDIT_PROMPTS = {
    "title": "📝 Yangi <b>nomni</b> yuboring:",
    "description": "📖 Yangi <b>tavsifni</b> yuboring:",
    "genre": "🏷 Yangi <b>janrni</b> yuboring:",
    "year": "📅 Yangi <b>yilni</b> yuboring (masalan: 2023):",
    "status": "📌 Yangi <b>holatni</b> tanlang:",
    "poster": "🖼 Yangi <b>poster</b> rasmini yuboring:",
}


@router.message(F.text == "✏️ Tahrirlash")
async def edit_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(EditAnime.anime_id)
    await message.answer("🆔 Tahrirlamoqchi bo'lgan animening <b>ID</b> raqamini yuboring:", reply_markup=kb.cancel_kb())


@router.message(EditAnime.anime_id)
async def edit_pick_anime(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    anime = await db.get_anime_by_id(int(t)) if t.isdigit() else None
    if not anime:
        await message.answer("❗️ Bunday ID li anime topilmadi. Qaytadan yuboring.", reply_markup=kb.cancel_kb())
        return
    await state.clear()
    await message.answer("✏️ Tahrirlash", reply_markup=kb.admin_menu_kb())
    await message.answer(
        f"🎬 <b>{html.escape(anime['title'])}</b> (ID: <code>{anime['id']}</code>)\n\n"
        "Qaysi maydonni o'zgartirmoqchisiz?",
        reply_markup=kb.edit_fields_kb(anime["id"]),
    )


@router.callback_query(kb.EditFieldCB.filter())
async def edit_pick_field(callback: CallbackQuery, callback_data: kb.EditFieldCB, state: FSMContext):
    anime = await db.get_anime_by_id(callback_data.id)
    if not anime:
        await callback.answer("Bu anime o'chirilgan.", show_alert=True)
        return
    field = callback_data.field
    if field not in EDIT_PROMPTS:
        await callback.answer("Noma'lum maydon.", show_alert=True)
        return
    await state.clear()
    await state.set_state(EditAnime.value)
    await state.update_data(anime_id=anime["id"], field=field)
    if field == "status":
        await callback.message.answer(EDIT_PROMPTS[field], reply_markup=kb.status_choice_kb())
    else:
        await callback.message.answer(EDIT_PROMPTS[field], reply_markup=kb.cancel_kb())
    await callback.answer()


@router.callback_query(EditAnime.value, F.data.startswith("status_"))
async def edit_status(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("field") != "status":
        await callback.answer()
        return
    status = callback.data.removeprefix("status_")
    await db.update_anime_field(data["anime_id"], "status", status)
    await state.clear()
    await _edit(callback, f"✅ Holat yangilandi: <b>{html.escape(status)}</b>", None)
    await callback.message.answer("Tayyor.", reply_markup=kb.admin_menu_kb())
    await callback.answer()


@router.message(EditAnime.value)
async def edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field")
    anime_id = data.get("anime_id")

    if field == "status":
        await message.answer("Yuqoridagi tugmalardan birini tanlang yoki ❌ Bekor qilish tugmasini bosing.")
        return

    if field == "poster":
        if not message.photo:
            await message.answer("❗️ Rasm yuboring.")
            return
        value = message.photo[-1].file_id
    elif field == "year":
        t = (message.text or "").strip()
        if not (t.isdigit() and 1900 <= int(t) <= 2100):
            await message.answer("❗️ Yilni raqam bilan yuboring (masalan: 2023).")
            return
        value = int(t)
    else:
        value = (message.text or "").strip()
        if not value:
            await message.answer("❗️ Matn yuboring.")
            return

    await db.update_anime_field(anime_id, field, value)
    await state.clear()
    await message.answer("✅ Yangilandi.", reply_markup=kb.admin_menu_kb())


# ---------------------------------------------------------------
# 🗑 ANIME O'CHIRISH
# ---------------------------------------------------------------
@router.message(F.text == "🗑 Anime o'chirish")
async def delete_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(DeleteAnime.anime_id)
    await message.answer("🆔 O'chirmoqchi bo'lgan animening <b>ID</b> raqamini yuboring:", reply_markup=kb.cancel_kb())


@router.message(DeleteAnime.anime_id)
async def delete_pick(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    anime = await db.get_anime_by_id(int(t)) if t.isdigit() else None
    if not anime:
        await message.answer("❗️ Bunday ID li anime topilmadi. Qaytadan yuboring.", reply_markup=kb.cancel_kb())
        return
    await state.clear()
    await message.answer("🗑 O'chirish", reply_markup=kb.admin_menu_kb())
    await message.answer(
        f"❓ <b>{html.escape(anime['title'])}</b> (ID: <code>{anime['id']}</code>) "
        "barcha qismlari bilan birga o'chirilsinmi?",
        reply_markup=kb.confirm_delete_kb(anime["id"]),
    )


@router.callback_query(kb.ConfirmCB.filter(F.action == "delete_anime"))
async def delete_confirm(callback: CallbackQuery, callback_data: kb.ConfirmCB):
    await db.delete_anime(callback_data.id)
    await _edit(callback, "🗑 Anime o'chirildi.", None)
    await callback.answer("O'chirildi")


@router.callback_query(kb.ConfirmCB.filter(F.action == "cancel"))
async def delete_cancel(callback: CallbackQuery):
    await _edit(callback, "Bekor qilindi.", None)
    await callback.answer()


# ---------------------------------------------------------------
# 📊 STATISTIKA
# ---------------------------------------------------------------
@router.message(F.text == "📊 Statistika")
async def stats(message: Message, state: FSMContext):
    await state.clear()
    anime_n = await db.count_anime()
    ep_n = await db.count_episodes()
    user_n = await db.get_user_count()
    ch_n = await db.count_channels()
    top = await db.get_top_anime(5)

    lines = [
        "📊 <b>Statistika</b>\n",
        f"🎬 Animelar: <b>{anime_n}</b>",
        f"🎞 Qismlar: <b>{ep_n}</b>",
        f"👥 Foydalanuvchilar: <b>{user_n}</b>",
        f"🔐 Majburiy kanallar: <b>{ch_n}</b>",
    ]
    if top:
        lines.append("\n🔥 <b>Eng ko'p ko'rilganlar:</b>")
        for i, a in enumerate(top, 1):
            lines.append(f"{i}. {html.escape(a['title'])} — 👁 {a['views']}")
    await message.answer("\n".join(lines), reply_markup=kb.admin_menu_kb())


# ---------------------------------------------------------------
# 📢 XABAR YUBORISH
# ---------------------------------------------------------------
@router.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Broadcast.content)
    await message.answer(
        "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring "
        "(matn, rasm, video — istalgani).\n\n"
        "⚠️ Xabarni yuborishingiz bilan darhol tarqatiladi.",
        reply_markup=kb.cancel_kb(),
    )


async def _copy_to(message: Message, uid: int) -> bool:
    try:
        await message.copy_to(uid)
        return True
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await message.copy_to(uid)
            return True
        except Exception:
            return False
    except Exception:
        return False


@router.message(Broadcast.content)
async def broadcast_send(message: Message, state: FSMContext):
    await state.clear()
    ids = await db.get_all_user_ids()
    await message.answer(f"📤 Yuborilmoqda... ({len(ids)} ta foydalanuvchi)")
    ok = fail = 0
    for uid in ids:
        if await _copy_to(message, uid):
            ok += 1
        else:
            fail += 1
        await asyncio.sleep(0.05)
    await message.answer(
        f"✅ Yuborildi: <b>{ok}</b>\n❌ Yetib bormadi: <b>{fail}</b>",
        reply_markup=kb.admin_menu_kb(),
    )


# ---------------------------------------------------------------
# 🔐 MAJBURIY OBUNA
# ---------------------------------------------------------------
@router.message(F.text == "🔐 Majburiy obuna")
async def force_sub_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🔐 <b>Majburiy obuna kanallari</b>", reply_markup=kb.obuna_menu_kb())


@router.message(F.text == "➕ Kanal qo'shish")
async def channel_add_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AddChannel.target)
    await message.answer(
        "Kanalni qo'shish uchun quyidagilardan birini yuboring:\n\n"
        "• kanalning <b>@username</b> i\n"
        "• kanal <b>ID</b> raqami (masalan: <code>-1001234567890</code>)\n"
        "• yoki kanaldan biror postni <b>forward</b> qiling\n\n"
        "⚠️ Bot o'sha kanalda <b>admin</b> bo'lishi shart, aks holda obunani tekshira olmaydi.",
        reply_markup=kb.cancel_kb(),
    )


@router.message(AddChannel.target)
async def channel_add(message: Message, state: FSMContext, bot: Bot):
    chat_ref = None
    origin = message.forward_origin
    if origin is not None and getattr(origin, "type", None) == "channel":
        chat_ref = origin.chat.id
    elif message.text:
        t = message.text.strip()
        if t.startswith("@") or re.fullmatch(r"-?\d+", t):
            chat_ref = t

    if chat_ref is None:
        await message.answer(
            "❗️ Tushunmadim. @username, ID yuboring yoki kanaldan post forward qiling.",
            reply_markup=kb.cancel_kb(),
        )
        return

    try:
        chat = await bot.get_chat(chat_ref)
    except Exception:
        await message.answer(
            "❗️ Kanal topilmadi. Bot kanalga admin sifatida qo'shilganini tekshiring.",
            reply_markup=kb.cancel_kb(),
        )
        return

    existing = await db.get_all_channels()
    if any(str(c["channel_id"]) == str(chat.id) for c in existing):
        await message.answer("ℹ️ Bu kanal allaqachon qo'shilgan.", reply_markup=kb.cancel_kb())
        return

    link = f"https://t.me/{chat.username}" if chat.username else None
    if not link:
        try:
            link = (await bot.create_chat_invite_link(chat.id)).invite_link
        except Exception:
            link = None
    if not link:
        await message.answer(
            "❗️ Taklif havolasini olib bo'lmadi. Botga kanalda admin huquqi "
            "(havola yaratish ruxsati bilan) bering va qaytadan urinib ko'ring.",
            reply_markup=kb.cancel_kb(),
        )
        return

    title = chat.title or str(chat.id)
    await db.add_channel(str(chat.id), title, link)
    await state.clear()
    await message.answer(f"✅ <b>{html.escape(title)}</b> majburiy obunaga qo'shildi.", reply_markup=kb.obuna_menu_kb())


async def _channels_view():
    channels = await db.get_all_channels()
    if not channels:
        return "🔐 Hozircha majburiy kanallar yo'q.", None
    lines = [f"🔐 <b>Majburiy kanallar</b> ({len(channels)} ta):\n"]
    for c in channels:
        lines.append(f"• {html.escape(c['title'])}")
    lines.append("\nO'chirish uchun kanal tugmasini bosing 👇")
    return "\n".join(lines), kb.channels_list_kb(channels)


@router.message(F.text == "📋 Kanallar ro'yxati")
async def channels_list(message: Message, state: FSMContext):
    await state.clear()
    text, markup = await _channels_view()
    await message.answer(text, reply_markup=markup)


@router.callback_query(kb.ChannelCB.filter(F.action == "delete"))
async def channel_delete(callback: CallbackQuery, callback_data: kb.ChannelCB):
    await db.delete_channel(callback_data.id)
    text, markup = await _channels_view()
    await _edit(callback, text, markup)
    await callback.answer("🗑 O'chirildi")


# ---------------------------------------------------------------
# 👥 ADMINLAR MENYUSI
# ---------------------------------------------------------------
@router.message(F.text == "👥 Adminlar")
async def admins_menu(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not perm.is_admin(uid):
        return
    await state.clear()
    if not perm.can_add_admins(uid):
        await message.answer("⛔️ Adminlarni boshqarish ruxsati sizda yo'q.")
        return
    await message.answer("👥 <b>Adminlarni boshqarish</b>", reply_markup=admins_menu_kb())


@router.message(F.text == "📋 Adminlar ro'yxati")
async def admins_list(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not perm.can_add_admins(uid):
        return
    await state.clear()
    text, markup = await render_list(uid)
    await message.answer(text, reply_markup=markup)


# ---------------------------------------------------------------
# ➕ ADMIN QO'SHISH
# ---------------------------------------------------------------
@router.message(F.text == "➕ Admin qo'shish")
async def add_admin_start(message: Message, state: FSMContext):
    if not perm.can_add_admins(message.from_user.id):
        return
    await state.clear()
    await state.set_state(AddAdmin.target)
    await message.answer(
        "Yangi adminni qo'shish uchun quyidagilardan birini yuboring:\n\n"
        "• <b>@username</b>\n"
        "• Telegram <b>ID</b> raqami\n"
        "• yoki o'sha odamning biror xabarini <b>forward</b> qiling\n\n"
        "ℹ️ @username bo'yicha qo'shilganda, u botga /start bosganida avtomatik admin bo'ladi.",
        reply_markup=kb.cancel_kb(),
    )


@router.message(StateFilter(AddAdmin), F.text == "❌ Bekor qilish")
async def add_admin_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=admins_menu_kb())


@router.message(AddAdmin.target)
async def add_admin_target(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    if not perm.can_add_admins(uid):
        await state.clear()
        return

    user_id = None
    username = None

    origin = message.forward_origin
    if origin is not None and getattr(origin, "type", None) == "user":
        user_id = origin.sender_user.id
        username = origin.sender_user.username
    elif message.text:
        t = message.text.strip()
        if t.isdigit():
            user_id = int(t)
        else:
            m = USERNAME_RE.fullmatch(t)
            if m:
                username = m.group(1)

    if user_id is None and username is None:
        await message.answer(
            "❗️ Tushunmadim. @username, ID raqam yuboring yoki xabarini forward qiling "
            "(yashirin profilli odamning xabari ishlamaydi).",
            reply_markup=kb.cancel_kb(),
        )
        return

    if user_id is None and username:
        user_id = await perm.find_user_id_by_username(username)

    if perm.already_admin(user_id, username):
        await message.answer("ℹ️ Bu foydalanuvchi allaqachon admin.", reply_markup=kb.cancel_kb())
        return

    # Faqat super adminlar "admin qo'sha oladi" ruxsatini bera oladi
    if perm.is_super(uid):
        await state.update_data(user_id=user_id, username=username)
        await state.set_state(AddAdmin.permission)
        await message.answer(
            f"<b>{perm.label(user_id, username)}</b> uchun ruxsatni tanlang:",
            reply_markup=permission_choice_kb(),
        )
    else:
        text = await finish_add(bot, uid, user_id, username, can_add=False)
        await state.clear()
        await message.answer(text, reply_markup=admins_menu_kb())


@router.message(AddAdmin.permission)
async def add_admin_permission_reminder(message: Message):
    await message.answer("Yuqoridagi tugmalardan birini tanlang yoki ❌ Bekor qilish tugmasini bosing.")


@router.callback_query(NewAdminCB.filter(), AddAdmin.permission)
async def add_admin_permission(callback: CallbackQuery, callback_data: NewAdminCB, state: FSMContext, bot: Bot):
    uid = callback.from_user.id
    if not perm.is_super(uid):
        await callback.answer("⛔️ Faqat super adminlar.", show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    text = await finish_add(
        bot, uid, data.get("user_id"), data.get("username"), can_add=bool(callback_data.can_add)
    )
    await _edit(callback, text, None)
    await callback.message.answer("👥 Adminlarni boshqarish", reply_markup=admins_menu_kb())
    await callback.answer()


async def finish_add(bot: Bot, adder_id: int, user_id, username, can_add: bool) -> str:
    await perm.add_admin(user_id, username, can_add, adder_id)
    role = "admin + admin qo'sha oladi" if can_add else "admin"
    text = f"✅ <b>{perm.label(user_id, username)}</b> — {role} qilib qo'shildi."
    if user_id is not None:
        try:
            await bot.send_message(
                user_id, "🎉 Siz botga admin qilib tayinlandingiz!\n🛠 Admin panelni ochish: /admin"
            )
        except Exception:
            text += "\n\nℹ️ Unga xabar yuborib bo'lmadi (botga hali /start bosmagan bo'lishi mumkin)."
    else:
        text += "\n\nℹ️ U botga /start bosganida avtomatik admin bo'ladi."
    return text


# ---------------------------------------------------------------
# ADMINNI BOSHQARISH (faqat super adminlar)
# ---------------------------------------------------------------
@router.callback_query(AdmCB.filter())
async def manage_admin(callback: CallbackQuery, callback_data: AdmCB, bot: Bot):
    uid = callback.from_user.id
    if not perm.is_super(uid):
        await callback.answer("⛔️ Faqat super adminlar boshqara oladi.", show_alert=True)
        return

    action = callback_data.action

    if action == "list":
        text, markup = await render_list(uid)
        await _edit(callback, text, markup)
        await callback.answer()
        return

    row = await perm.get_row(callback_data.id)
    if not row or row["is_super"]:
        await callback.answer("Topilmadi.", show_alert=True)
        return

    if action == "open":
        text, markup = detail_view(row)
        await _edit(callback, text, markup)

    elif action == "toggle":
        await perm.set_can_add(row["id"], not bool(row["can_add"]))
        row = await perm.get_row(row["id"])
        text, markup = detail_view(row)
        await _edit(callback, text, markup)
        await callback.answer("✅ Yangilandi")
        return

    elif action == "ask_del":
        b = InlineKeyboardBuilder()
        b.button(text="✅ Ha, olib tashlash", callback_data=AdmCB(id=row["id"], action="del"))
        b.button(text="❌ Yo'q", callback_data=AdmCB(id=row["id"], action="open"))
        b.adjust(2)
        await _edit(callback, f"❓ <b>{perm.row_label(row)}</b> ni adminlikdan olib tashlaysizmi?", b.as_markup())

    elif action == "del":
        await perm.remove_admin(row["id"])
        if row.get("user_id") is not None:
            try:
                await bot.send_message(row["user_id"], "ℹ️ Siz adminlikdan olib tashlandingiz.")
            except Exception:
                pass
        text, markup = await render_list(uid)
        await _edit(callback, "🗑 Adminlikdan olib tashlandi.\n\n" + text, markup)
        await callback.answer("🗑 Olib tashlandi")
        return

    await callback.answer()