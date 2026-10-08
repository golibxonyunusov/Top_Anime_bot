from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import ADMIN_IDS
import keyboards as kb
from subscription import get_missing_channels


class ForceSubMiddleware(BaseMiddleware):
    """
    Har bir kelgan xabar/tugma bosilishidan oldin ishga tushadi.
    Agar foydalanuvchi majburiy kanal(lar)ga a'zo bo'lmasa, asosiy
    handlerga o'tkazmasdan, obuna bo'lish so'rovini ko'rsatadi.
    Adminlar va "✅ A'zo bo'ldim" tugmasi bu tekshiruvdan chetlanadi.
    """

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        if user.id in ADMIN_IDS:
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)

        bot = data["bot"]
        missing = await get_missing_channels(bot, user.id)
        if not missing:
            return await handler(event, data)

        text = (
            "🔐 <b>Botdan foydalanish uchun</b> quyidagi kanal(lar)ga a'zo bo'ling, "
            "so'ng «✅ A'zo bo'ldim» tugmasini bosing:"
        )
        markup = kb.force_sub_kb(missing)

        if isinstance(event, CallbackQuery):
            try:
                await event.message.answer(text, reply_markup=markup)
            except Exception:
                pass
            await event.answer()
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=markup)

        return  # asosiy handlerga o'tkazilmaydi — oqim shu yerda to'xtaydi
