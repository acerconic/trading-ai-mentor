"""
Internationalization (i18n) module.
All bot UI strings in RU and UZ.
Usage: from utils.i18n import t
       t("key", lang)   →  returns string in the given language
"""
from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {

    # ── Start / auth ────────────────────────────────────────────────────────
    "welcome_admin": {
        "RU": "👋 Добро пожаловать, Администратор!\nПожалуйста, выберите язык:",
        "UZ": "👋 Xush kelibsiz, Administrator!\nIltimos, tilni tanlang:",
    },
    "welcome_back": {
        "RU": "👋 Добро пожаловать обратно!",
        "UZ": "👋 Qaytib xush kelibsiz!",
    },
    "access_denied": {
        "RU": "🔒 Доступ закрыт. Ваша заявка отправлена администратору.",
        "UZ": "🔒 Kirish yopiq. Arizangiz administratorga yuborildi.",
    },
    "pending_approval": {
        "RU": "⏳ Ваша заявка ещё на рассмотрении.",
        "UZ": "⏳ Arizangiz hali ko'rib chiqilmoqda.",
    },
    "choose_language": {
        "RU": "🌐 Пожалуйста, выберите язык / Iltimos, tilni tanlang:",
        "UZ": "🌐 Iltimos, tilni tanlang / Пожалуйста, выберите язык:",
    },
    "admin_restored": {
        "RU": "✅ Доступ Администратора восстановлен! Выберите язык:",
        "UZ": "✅ Administrator kirish tiklandi! Tilni tanlang:",
    },

    # ── Language change ──────────────────────────────────────────────────────
    "lang_changed_ru": {
        "RU": "✅ Язык изменён на <b>Русский 🇷🇺</b>!\n\nЧто бы вы хотели сделать?",
        "UZ": "✅ Til <b>Ruscha 🇷🇺</b> ga o'zgartirildi!\n\nNima qilmoqchisiz?",
    },
    "lang_changed_uz": {
        "RU": "✅ Язык изменён на <b>O'zbekcha 🇺🇿</b>!\n\nЧто бы вы хотели сделать?",
        "UZ": "✅ Til <b>O'zbekcha 🇺🇿</b> ga o'zgartirildi!\n\nNima qilmoqchisiz?",
    },
    "lang_prompt": {
        "RU": "🌐 Выберите язык / Tilni tanlang:",
        "UZ": "🌐 Tilni tanlang / Выберите язык:",
    },

    # ── Main menu buttons ───────────────────────────────────────────────────
    "btn_new_topic": {
        "RU": "📚 Новая тема",
        "UZ": "📚 Yangi mavzu",
    },
    "btn_practice": {
        "RU": "📝 Практика",
        "UZ": "📝 Amaliyot",
    },
    "btn_profile": {
        "RU": "👤 Мой Профиль",
        "UZ": "👤 Mening Profilim",
    },
    "btn_language": {
        "RU": "🌐 Язык",
        "UZ": "🌐 Til",
    },
    "btn_reset": {
        "RU": "🧹 Сброс памяти",
        "UZ": "🧹 Xotirani tozalash",
    },
    "btn_admin": {
        "RU": "🔧 Admin Panel",
        "UZ": "🔧 Admin Panel",
    },

    # ── Study / PDF ──────────────────────────────────────────────────────────
    "send_pdf": {
        "RU": (
            "📘 Отправьте мне <b>PDF-книгу</b> по трейдингу для начала учёбы.\n\n"
            "<i>Ограничений по количеству страниц и размеру нет!</i>"
        ),
        "UZ": (
            "📘 O'qitishni boshlash uchun menga savdo bo'yicha <b>PDF-kitob</b> yuboring.\n\n"
            "<i>Sahifalar soni va fayl hajmida cheklov yo'q!</i>"
        ),
    },
    "pdf_loading": {
        "RU": "📥 Загружаю PDF…\n⏳ Определяю тип документа.",
        "UZ": "📥 PDF yuklanmoqda…\n⏳ Hujjat turi aniqlanmoqda.",
    },
    "pdf_scanned_detected": {
        "RU": "📡 Обнаружен <b>сканированный PDF</b> ({n} стр.).\n🤖 Читаю через Vision AI…",
        "UZ": "📡 <b>Skanerlangan PDF</b> aniqlandi ({n} bet).\n🤖 Vision AI orqali o'qiyapman…",
    },
    "pdf_text_detected": {
        "RU": "📄 Текстовый PDF: <b>{n} стр. с теорией</b>.",
        "UZ": "📄 Matnli PDF: <b>{n} bet nazariya</b>.",
    },
    "pdf_no_openrouter": {
        "RU": (
            "❌ Этот PDF содержит только сканированные изображения.\n\n"
            "Для чтения сканов нужен <b>OPENROUTER_API_KEY</b>."
        ),
        "UZ": (
            "❌ Bu PDF faqat skanerlangan rasmlarni o'z ichiga oladi.\n\n"
            "Skanlarni o'qish uchun <b>OPENROUTER_API_KEY</b> kerak."
        ),
    },
    "pdf_corrupted": {
        "RU": "❌ Ошибка при чтении PDF. Файл может быть повреждён.",
        "UZ": "❌ PDF o'qishda xatolik. Fayl shikastlangan bo'lishi mumkin.",
    },
    "page_analysing": {
        "RU": "📖 Анализирую страницу {cur} из {total}…",
        "UZ": "📖 {cur}/{total} - bet tahlil qilinmoqda…",
    },
    "page_ai_error": {
        "RU": "❌ Ошибка AI. Проверьте API-ключи и попробуйте ещё раз.",
        "UZ": "❌ AI xatosi. API kalitlarni tekshiring va qayta urinib ko'ring.",
    },
    "page_error": {
        "RU": "❌ Ошибка при обработке страницы. Попробуйте ещё раз.",
        "UZ": "❌ Betni qayta ishlashda xatolik. Qayta urinib ko'ring.",
    },
    "page_label": {
        "RU": "📄 <b>Страница {n}</b>",
        "UZ": "📄 <b>Bet {n}</b>",
    },
    "book_finished": {
        "RU": "🎉 <b>Книга полностью изучена!</b> Отличная работа! 🏆",
        "UZ": "🎉 <b>Kitob to'liq o'rganildi!</b> Zo'r ish! 🏆",
    },
    "explain_more_wait": {
        "RU": "🧠 ИИ переформулирует материал простым языком…",
        "UZ": "🧠 AI materialni oddiy tilda qayta tushuntiryapti…",
    },
    "explain_more_result": {
        "RU": "💡 <b>Простое объяснение:</b>",
        "UZ": "💡 <b>Oddiy tushuntirish:</b>",
    },
    "explain_more_error": {
        "RU": "❌ Не получилось сгенерировать объяснение. Попробуйте ещё раз.",
        "UZ": "❌ Tushuntirish yaratib bo'lmadi. Qayta urinib ko'ring.",
    },
    "ask_question_prompt": {
        "RU": "❓ Напишите свой вопрос или термин, который непонятен\n<i>(например: «Что такое Ордерблок?»)</i>:",
        "UZ": "❓ Tushunmagan savolingiz yoki atamangizni yozing\n<i>(masalan: «Orderblock nima?»)</i>:",
    },
    "answer_searching": {
        "RU": "🔍 Ищу ответ…",
        "UZ": "🔍 Javob qidirilmoqda…",
    },
    "answer_not_found": {
        "RU": "💡 Не удалось найти ответ. Попробуйте переформулировать вопрос.",
        "UZ": "💡 Javob topilmadi. Savolni boshqacha shaklda yozing.",
    },
    "answer_prefix": {
        "RU": "🤖 <b>AI Ментор:</b>",
        "UZ": "🤖 <b>AI Mentor:</b>",
    },
    "send_image_only": {
        "RU": "❌ Пожалуйста, отправьте файл в формате <b>PDF</b>.",
        "UZ": "❌ Iltimos, <b>PDF</b> formatdagi fayl yuboring.",
    },

    # ── Study keyboard buttons ───────────────────────────────────────────────
    "btn_next_page": {
        "RU": "✅ Всё понятно, идём дальше",
        "UZ": "✅ Tushunarli, davom etamiz",
    },
    "btn_explain_more": {
        "RU": "📖 Не понял, объясни иначе",
        "UZ": "📖 Tushunmadim, boshqacha tushuntir",
    },
    "btn_ask_question": {
        "RU": "❓ У меня вопрос",
        "UZ": "❓ Savolim bor",
    },

    # ── Practice ──────────────────────────────────────────────────────────────
    "practice_prompt": {
        "RU": (
            "📊 Пришлите <b>скриншот вашего графика</b> (PNG/JPG) с разметкой по SMC/ICT.\n\n"
            "🤖 Нейросеть проверит вашу работу и даст обратную связь."
        ),
        "UZ": (
            "📊 SMC/ICT bo'yicha belgilangan <b>grafik skrinshotingizni</b> (PNG/JPG) yuboring.\n\n"
            "🤖 Neyronset ishingizni tekshirib, fikr-mulohaza bildiradi."
        ),
    },
    "practice_analysing": {
        "RU": "🧠 Нейросеть анализирует ваш график…\n⏳ Пожалуйста, подождите.",
        "UZ": "🧠 Neyronset grafikingizni tahlil qilmoqda…\n⏳ Iltimos, kuting.",
    },
    "practice_result": {
        "RU": "📊 <b>Результат проверки:</b>",
        "UZ": "📊 <b>Tekshiruv natijasi:</b>",
    },
    "practice_api_error": {
        "RU": "❌ API не отвечает. Попробуйте ещё раз.",
        "UZ": "❌ API javob bermayapti. Qayta urinib ko'ring.",
    },
    "practice_image_only": {
        "RU": "❌ Пожалуйста, отправьте изображение (PNG или JPG).",
        "UZ": "❌ Iltimos, rasm yuboring (PNG yoki JPG).",
    },
    "practice_error": {
        "RU": "❌ Непредвиденная ошибка. Убедитесь, что отправили корректное изображение.",
        "UZ": "❌ Kutilmagan xato. To'g'ri rasm yuborganingizni tekshiring.",
    },

    # ── Profile ───────────────────────────────────────────────────────────────
    "profile_title": {
        "RU": "👤 <b>Профиль Трейдера</b>",
        "UZ": "👤 <b>Treyderning Profili</b>",
    },
    "profile_lang": {
        "RU": "🌐 <b>Язык:</b>",
        "UZ": "🌐 <b>Til:</b>",
    },
    "profile_rank": {
        "RU": "⭐ <b>Ранг:</b>",
        "UZ": "⭐ <b>Daraja:</b>",
    },
    "profile_stats": {
        "RU": "📊 <b>Статистика обучения:</b>",
        "UZ": "📊 <b>O'qish statistikasi:</b>",
    },
    "profile_books": {
        "RU": "📚 Книг изучено:",
        "UZ": "📚 Kitoblar o'rganildi:",
    },
    "profile_hw": {
        "RU": "🎯 Практик сдано:",
        "UZ": "🎯 Amaliyotlar topshirildi:",
    },
    "profile_fails": {
        "RU": "❌ Не сдал:",
        "UZ": "❌ Topshira olmadi:",
    },
    "profile_winrate": {
        "RU": "📈 <b>Винрейт:</b>",
        "UZ": "📈 <b>Yutuq darajasi:</b>",
    },
    "profile_not_found": {
        "RU": "❌ Профиль не найден.",
        "UZ": "❌ Profil topilmadi.",
    },
    "rank_beginner": {
        "RU": "🌱 Новичок",
        "UZ": "🌱 Yangi boshlovchi",
    },
    "rank_practitioner": {
        "RU": "📈 Практикант",
        "UZ": "📈 Amaliyotchi",
    },
    "rank_analyst": {
        "RU": "💡 Аналитик",
        "UZ": "💡 Tahlilchi",
    },
    "rank_trader": {
        "RU": "🎯 Трейдер SMC",
        "UZ": "🎯 SMC Treyderi",
    },
    "rank_master": {
        "RU": "🏆 Мастер ICT",
        "UZ": "🏆 ICT Ustasi",
    },
    "lang_not_set": {
        "RU": "Не выбран",
        "UZ": "Tanlanmagan",
    },

    # ── Reset ─────────────────────────────────────────────────────────────────
    "reset_done": {
        "RU": "🧹 Контекст сессии очищен! Начните с чистого листа.",
        "UZ": "🧹 Sessiya konteksti tozalandi! Yangi sahifadan boshlang.",
    },
}


def t(key: str, lang: str = "RU") -> str:
    """Get translated string. Falls back to RU if key/lang missing."""
    lang = (lang or "RU").upper()
    entry = _STRINGS.get(key)
    if not entry:
        return key  # return raw key so bugs are visible
    return entry.get(lang) or entry.get("RU") or key
