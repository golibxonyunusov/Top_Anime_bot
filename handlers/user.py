import math
from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest

import database as db
import keyboards as kb
from subscription import get_missing_channels
from config import ADMIN_IDS, WELCOME_TEXT, STUDIO_NAME, ANIME_PER_PAGE, EPISODES_PER_PAGE

router = Router()


class SearchState(StatesGroup):
    waiting_query = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------------------------------------------------------
# /start
# ---------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    # Kanaldagi "Botda ko'rish" tugmasidan kelgan: /start anime_<id>
    arg = (command.args or "").strip()
    if arg.startswith("anime_") and arg[6:].isdigit():
        anime = await db.get_anime_by_id(int(arg[6:]))
        if anime:
            await message.answer("🎬", reply_markup=kb.main_menu_kb(is_admin(message.from_user.id)))
            await show_anime_card(message, anime, message.from_user.id)
            return

    text = WELCOME_TEXT.format(studio=STUDIO_NAME)
    await message.answer(text, reply_markup=kb.main_menu_kb(is_admin(message.from_user.id)))


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery):
    missing = await get_missing_channels(callback.bot, callback.from_user.id)
    if missing:
        await callback.answer(
            "❗️ Hali barcha kanallarga a'zo bo'lmagansiz. A'zo bo'lgach, qaytadan urinib ko'ring.",
            show_alert=True,
        )
        return

    await db.add_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    text = WELCOME_TEXT.format(studio=STUDIO_NAME)
    await callback.message.answer(text, reply_markup=kb.main_menu_kb(is_admin(callback.from_user.id)))
    await callback.answer("✅ Rahmat!")


@router.message(F.text == "⬅️ Bosh menyu")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Bosh menyu", reply_markup=kb.main_menu_kb(is_admin(message.from_user.id)))


@router.message(F.text == "ℹ️ Yordam")
async def help_handler(message: Message):
    text = (
        f"ℹ️ <b>{STUDIO_NAME} — Yordam</b>\n\n"
        "🔎 <b>Qidirish</b> — anime nomini yoki uning <b>ID</b> raqamini yozib qidiring\n"
        "📋 <b>Barcha animelar</b> — bazadagi barcha animelar ro'yxati\n"
        "⭐ <b>Sevimlilar</b> — siz belgilagan sevimli animelar\n\n"
        "Har bir anime ID raqami orqali tez topiladi. Masalan: <code>7</code> deb yozsangiz, "
        "7-ID li anime chiqadi."
    )
    await message.answer(text)


# ---------------------------------------------------------------
# QIDIRISH
# ---------------------------------------------------------------
@router.message(F.text == "🔎 Qidirish")
async def search_start(message: Message, state: FSMContext):
    await state.set_state(SearchState.waiting_query)
    await message.answer(
        "🔎 Anime nomini yoki <b>ID</b> raqamini yuboring:",
        reply_markup=kb.cancel_kb(),
    )


@router.message(SearchState.waiting_query, F.text == "❌ Bekor qilish")
async def search_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=kb.main_menu_kb(is_admin(message.from_user.id)))


@router.message(SearchState.waiting_query)
async def search_process(message: Message, state: FSMContext):
    query = message.text.strip()

    if query.isdigit():
        anime = await db.get_anime_by_id(int(query))
        if anime:
            await state.clear()
            await show_anime_card(message, anime, message.from_user.id)
            await message.answer("Yana qidirishni davom ettirishingiz mumkin 👇", reply_markup=kb.main_menu_kb(is_admin(message.from_user.id)))
            return

    results = await db.search_anime_by_name(query)
    if not results:
        await message.answer(
            "😕 Hech narsa topilmadi. Boshqa nom yoki ID bilan urinib ko'ring, "
            "yoki ❌ Bekor qilish tugmasini bosing.",
            reply_markup=kb.cancel_kb(),
        )
        return

    if len(results) == 1:
        await state.clear()
        await show_anime_card(message, results[0], message.from_user.id)
        await message.answer("Yana qidirishni davom ettirishingiz mumkin 👇", reply_markup=kb.main_menu_kb(is_admin(message.from_user.id)))
        return

    await state.clear()
    text = f"🔎 <b>«{query}»</b> bo'yicha {len(results)} ta natija topildi:"
    markup = kb.anime_list_kb(results, scope="search", page=0, total_pages=1)
    await message.answer(text, reply_markup=markup)
    await message.answer("Yana qidirish uchun 🔎 Qidirish tugmasini bosing.", reply_markup=kb.main_menu_kb(is_admin(message.from_user.id)))


# ---------------------------------------------------------------
# BARCHA ANIMELAR / SEVIMLILAR (ro'yxatlar)
# ---------------------------------------------------------------
@router.message(F.text == "📋 Barcha animelar")
async def list_all(message: Message, state: FSMContext):
    await state.clear()
    await send_anime_page(message, scope="all", page=0, user_id=message.from_user.id)


@router.message(F.text == "⭐ Sevimlilar")
async def list_favorites(message: Message, state: FSMContext):
    await state.clear()
    await send_anime_page(message, scope="fav", page=0, user_id=message.from_user.id)


async def send_anime_page(message: Message, scope: str, page: int, user_id: int, edit: bool = False, cb: CallbackQuery = None):
    if scope == "all":
        total = await db.count_anime()
        total_pages = max(1, math.ceil(total / ANIME_PER_PAGE))
        rows = await db.get_all_anime(page, ANIME_PER_PAGE)
        title = f"📋 <b>Barcha animelar</b> ({total} ta)"
        if not rows:
            title = "📋 Hozircha bazada anime yo'q."
    else:
        favs = await db.get_favorites(user_id)
        total_pages = max(1, math.ceil(len(favs) / ANIME_PER_PAGE))
        start = page * ANIME_PER_PAGE
        rows = favs[start:start + ANIME_PER_PAGE]
        title = f"⭐ <b>Sevimli animelaringiz</b> ({len(favs)} ta)"
        if not favs:
            title = "⭐ Sizda hali sevimli animelar yo'q.\n\nAnime sahifasida ⭐ tugmasini bosib qo'shishingiz mumkin."

    markup = kb.anime_list_kb(rows, scope=scope, page=page, total_pages=total_pages) if rows else None

    if edit and cb:
        try:
            await cb.message.edit_text(title, reply_markup=markup)
        except TelegramBadRequest:
            pass
    else:
        await message.answer(title, reply_markup=markup)


@router.callback_query(kb.PageCB.filter(F.scope.in_(["all", "fav"])))
async def paginate_list(callback: CallbackQuery, callback_data: kb.PageCB):
    await send_anime_page(callback.message, callback_data.scope, callback_data.page, callback.from_user.id, edit=True, cb=callback)
    await callback.answer()


# ---------------------------------------------------------------
# ANIME KARTASINI KO'RSATISH
# ---------------------------------------------------------------
async def show_anime_card(message_or_cb, anime, user_id: int, edit: bool = False):
    episodes = await db.get_episodes(anime["id"])
    fav = await db.is_favorite(user_id, anime["id"])

    caption = (
        f"🎬 <b>{anime['title']}</b>\n"
        f"🆔 ID: <code>{anime['id']}</code>\n"
        f"🏷 Janr: {anime['genre'] or '—'}\n"
        f"📅 Yil: {anime['year'] or '—'}\n"
        f"📌 Holati: {anime['status']}\n"
        f"🎞 Qismlar soni: {len(episodes)}\n"
        f"👁 Ko'rishlar: {anime['views']}\n\n"
        f"{anime['description'] or ''}"
    )
    markup = kb.anime_card_kb(anime["id"], fav, bool(episodes))

    if edit:
        cb: CallbackQuery = message_or_cb
        try:
            if anime["poster"]:
                await cb.message.edit_media(InputMediaPhoto(media=anime["poster"], caption=caption), reply_markup=markup)
            else:
                await cb.message.edit_text(caption, reply_markup=markup)
        except TelegramBadRequest:
            pass
        return

    message: Message = message_or_cb
    if anime["poster"]:
        await message.answer_photo(anime["poster"], caption=caption, reply_markup=markup)
    else:
        await message.answer(caption, reply_markup=markup)


@router.callback_query(kb.AnimeCB.filter(F.action == "view"))
async def cb_view_anime(callback: CallbackQuery, callback_data: kb.AnimeCB):
    anime = await db.get_anime_by_id(callback_data.id)
    if not anime:
        await callback.answer("Bu anime o'chirilgan.", show_alert=True)
        return
    await show_anime_card(callback, anime, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(kb.AnimeCB.filter(F.action == "fav"))
async def cb_add_fav(callback: CallbackQuery, callback_data: kb.AnimeCB):
    await db.add_favorite(callback.from_user.id, callback_data.id)
    anime = await db.get_anime_by_id(callback_data.id)
    if anime:
        await show_anime_card(callback, anime, callback.from_user.id, edit=True)
    await callback.answer("⭐ Sevimlilarga qo'shildi!")


@router.callback_query(kb.AnimeCB.filter(F.action == "unfav"))
async def cb_remove_fav(callback: CallbackQuery, callback_data: kb.AnimeCB):
    await db.remove_favorite(callback.from_user.id, callback_data.id)
    anime = await db.get_anime_by_id(callback_data.id)
    if anime:
        await show_anime_card(callback, anime, callback.from_user.id, edit=True)
    await callback.answer("Sevimlilardan olib tashlandi.")


# ---------------------------------------------------------------
# QISMLAR (EPISODES)
# ---------------------------------------------------------------
@router.callback_query(kb.AnimeCB.filter(F.action == "episodes"))
async def cb_show_episodes(callback: CallbackQuery, callback_data: kb.AnimeCB):
    anime = await db.get_anime_by_id(callback_data.id)
    if not anime:
        await callback.answer("Bu anime o'chirilgan.", show_alert=True)
        return
    episodes = await db.get_episodes(anime["id"])
    if not episodes:
        await callback.answer("Hozircha qismlar yuklanmagan.", show_alert=True)
        return

    text = f"🎬 <b>{anime['title']}</b>\n\nKerakli qismni tanlang:"
    markup = kb.episodes_kb(anime["id"], episodes, page=0, per_page=EPISODES_PER_PAGE)
    try:
        if anime["poster"]:
            await callback.message.edit_caption(caption=text, reply_markup=markup)
        else:
            await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.callback_query(kb.PageCB.filter(F.scope == "episodes"))
async def cb_paginate_episodes(callback: CallbackQuery, callback_data: kb.PageCB):
    anime = await db.get_anime_by_id(callback_data.anime_id)
    if not anime:
        await callback.answer("Bu anime o'chirilgan.", show_alert=True)
        return
    episodes = await db.get_episodes(anime["id"])
    text = f"🎬 <b>{anime['title']}</b>\n\nKerakli qismni tanlang:"
    markup = kb.episodes_kb(anime["id"], episodes, page=callback_data.page, per_page=EPISODES_PER_PAGE)
    try:
        if anime["poster"]:
            await callback.message.edit_caption(caption=text, reply_markup=markup)
        else:
            await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.callback_query(kb.EpisodeCB.filter())
async def cb_send_episode(callback: CallbackQuery, callback_data: kb.EpisodeCB):
    episode = await db.get_episode(callback_data.ep_id)
    anime = await db.get_anime_by_id(callback_data.anime_id)
    if not episode or not anime:
        await callback.answer("Bu qism topilmadi.", show_alert=True)
        return

    await db.increment_views(anime["id"])
    caption = f"🎬 {anime['title']} — {episode['episode_number']}-qism\n{STUDIO_NAME}"
    await callback.message.answer_video(episode["file_id"], caption=caption, reply_markup=kb.back_to_anime_kb(anime["id"]))
    await callback.answer("Yuklanmoqda... 🎬")


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()