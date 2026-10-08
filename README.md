# Top_ANIME — Telegram Bot

O'zbek tilida dublyaj qilingan anime'larni ulashish uchun Telegram bot.
Adminlar anime va uning qismlarini (video) qo'shadi, foydalanuvchilar esa
anime nomi yoki **ID raqami** orqali tez qidirib topadi.

## ✨ Imkoniyatlar

**Foydalanuvchilar uchun:**
- 🔎 Anime nomi yoki ID raqami bo'yicha qidirish
- 📋 Barcha animelar ro'yxati (sahifalab ko'rsatiladi)
- ⭐ Sevimlilar ro'yxati (shaxsiy)
- 🎬 Har bir anime uchun qismlar ro'yxati va videoni to'g'ridan-to'g'ri yuborish
- 👁 Ko'rishlar soni avtomatik hisoblanadi
- Chiroyli, tugmali va tushunarli interfeys

**Adminlar uchun (`/admin` yoki "🛠 Admin panel" tugmasi):**
- ➕ Yangi anime qo'shish (nomi, tavsifi, janri, yili, holati, posteri)
- 🎬 Anime'ga bir nechta video qism ketma-ket qo'shish
- ✏️ Har qanday anime maydonini tahrirlash (nomi, tavsifi, janri, yili, holati, posteri)
- 🗑 Anime'ni tasdiqlash bilan o'chirish (barcha qismlari bilan birga)
- 📊 Statistika (jami anime, qism, foydalanuvchilar soni, eng ko'p ko'rilganlar)
- 📢 Barcha foydalanuvchilarga xabar yuborish (matn/rasm/video — barchasi qo'llab-quvvatlanadi)
- Bir nechta admin qo'shish imkoniyati

## ⚙️ O'rnatish

### 1. Talablar
- Python 3.10 yoki undan yuqori versiyasi

### 2. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 3. Botni sozlash
`config.py` faylini oching va quyidagilarni to'ldiring:

```python
BOT_TOKEN = "123456789:AAAA..."   # @BotFather dan olingan token
ADMIN_IDS = [123456789]           # sizning Telegram ID raqamingiz
```

> 🔑 **Token olish:** Telegram'da [@BotFather](https://t.me/BotFather) ga yozing → `/newbot` →
> ko'rsatmalarga amal qiling → sizga token beriladi.
>
> 🆔 **O'z ID raqamingizni bilish:** [@userinfobot](https://t.me/userinfobot) ga `/start` yozing,
> u sizga ID raqamingizni yuboradi.

Bir nechta admin qo'shish uchun ro'yxatga vergul bilan qo'shing:
```python
ADMIN_IDS = [123456789, 987654321]
```

### 4. Botni ishga tushirish
```bash
python bot.py
```

Terminalda `🍥 UzumDub Studio bot ishga tushdi...` degan xabarni ko'rsangiz — tayyor!

## 📖 Foydalanish qo'llanmasi

### Anime qo'shish (admin)
1. `🛠 Admin panel` → `➕ Anime qo'shish`
2. Nomi, tavsifi, janri, yili, holati va posterini ketma-ket kiriting
   (tavsif/janr/yil/posterni o'tkazib yuborish ham mumkin)
3. Bot sizga anime **ID raqamini** beradi — shu raqamni eslab qoling,
   qism qo'shishda kerak bo'ladi

### Qism (video) qo'shish (admin)
1. `🛠 Admin panel` → `🎬 Qism qo'shish`
2. Anime ID sini kiriting
3. Qism raqamini kiriting (masalan `1`), so'ng video faylni yuboring
4. Bot avtomatik keyingi qism raqamini so'raydi — shu tarzda barcha
   qismlarni ketma-ket qo'shishingiz mumkin
5. Tugatgach `✅ Yakunlash` tugmasini bosing

### Qidirish (foydalanuvchi)
`🔎 Qidirish` tugmasini bosib, anime nomini (masalan `Naruto`) yoki
uning ID raqamini (masalan `1`) yuboring — bot mos animeni topib beradi.

## 🗂 Loyiha tuzilishi
```
uzumdub_bot/
├── bot.py              # botni ishga tushiruvchi asosiy fayl
├── config.py            # token, admin ID'lar va sozlamalar
├── database.py           # SQLite bilan ishlash (barcha DB funksiyalari)
├── keyboards.py           # barcha tugmalar (reply va inline)
├── requirements.txt
└── handlers/
    ├── user.py           # oddiy foydalanuvchi funksiyalari
    └── admin.py           # admin funksiyalari
```

Ma'lumotlar `uzumdub.db` nomli SQLite faylida saqlanadi — bu fayl birinchi
ishga tushirishda avtomatik yaratiladi, hech qanday qo'shimcha server
(MySQL, PostgreSQL va h.k.) kerak emas.

## 🚀 24/7 ishlashi uchun

Kompyuteringizni o'chirsangiz bot ham to'xtaydi. Doimiy ishlashi uchun
botni VPS (masalan Timeweb, Hetzner) yoki serverga joylashtirib, orqa fonda
`systemd`, `pm2` yoki `screen`/`tmux` yordamida ishga tushiring, masalan:

```bash
screen -S uzumdub_bot
python bot.py
# Ctrl+A keyin D bosib screen'dan chiqing, bot orqa fonda ishlayveradi
```

## 🛠 Kengaytirish g'oyalari
- Majburiy kanalga a'zolik tekshiruvi
- Anime'larni janr bo'yicha filtrlash tugmalari
- Inline rejim (`@botusername anime nomi` — istalgan chatda qidirish)
- Reyting/izoh qoldirish tizimi
# AnorDubStudio
