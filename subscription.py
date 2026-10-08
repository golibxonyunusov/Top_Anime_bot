import database as db


async def get_missing_channels(bot, user_id: int):
    """Foydalanuvchi hali a'zo bo'lmagan majburiy kanallar ro'yxatini qaytaradi."""
    channels = await db.get_all_channels()
    if not channels:
        return []

    missing = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=int(ch["channel_id"]), user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception as e:
            # Bot o'sha kanalda admin bo'lmasa yoki kanal topilmasa — shu kanalni
            # tekshirishni o'tkazib yuboramiz (butun botni bloklab qo'ymaslik uchun).
            print(f"⚠️ Majburiy obuna tekshiruvida xato ({ch.get('title')}): {e}")
            continue
    return missing
