import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database import Database
from config import ADMIN_ID
from handlers.start import get_main_menu
from utils.states import StudyState, PracticeState

menu_router = Router()
logger = logging.getLogger(__name__)


@menu_router.callback_query(F.data.in_(["lang_ru", "lang_uz"]))
async def process_language_selection(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = "RU" if callback.data == "lang_ru" else "UZ"

    await Database.update_language(user_id, lang)

    try:
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения выбора языка: {e}")

    await callback.message.answer(
        f"✅ Язык успешно изменён на <b>{lang}</b>!\n\nЧто бы вы хотели сделать далее?",
        reply_markup=get_main_menu(user_id),
        parse_mode="HTML"
    )
    await callback.answer()


@menu_router.message(F.text == "📚 Новая тема")
async def start_new_topic(message: Message, state: FSMContext):
    await message.answer(
        "📘 Отправьте мне <b>PDF-книгу или документ</b> по трейдингу для начала учёбы.\n\n"
        "<i>Лимиты на количество страниц и размер файла отсутствуют!</i>",
        parse_mode="HTML"
    )
    await state.set_state(StudyState.waiting_for_pdf)


@menu_router.message(F.text == "📝 Практика")
async def start_practice(message: Message, state: FSMContext):
    await message.answer(
        "📊 Пришлите мне <b>скриншот вашего графика</b> (PNG/JPG) с вашей разметкой по SMC/ICT.\n\n"
        "🤖 Нейросеть проверит вашу работу и даст обратную связь.",
        parse_mode="HTML"
    )
    await state.set_state(PracticeState.waiting_for_chart)


@menu_router.message(F.text == "👤 Мой Профиль")
async def show_profile(message: Message):
    user_id = message.from_user.id
    user = await Database.get_user(user_id)

    if not user:
        await message.answer("Профиль не найден.")
        return

    stats = await Database.get_stats(user_id)
    winrate = stats.get("winrate", 0.0)

    # Determine rank emoji
    books = stats.get("studied_books", 0)
    rank = "🌱 Новичок"
    if books >= 3:
        rank = "📈 Практикант"
    if books >= 7:
        rank = "💡 Аналитик"
    if books >= 15:
        rank = "🎯 Трейдер SMC"
    if books >= 25:
        rank = "🏆 Мастер ICT"

    profile_text = (
        f"👤 <b>Профиль Трейдера</b> @{user['username']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Язык:</b> {user['language'] or 'Не выбран'}\n"
        f"⭐ <b>Ранг:</b> {rank}\n\n"
        f"📊 <b>Статистика обучения:</b>\n"
        f"  📚 Книг изучено: <b>{books}</b>\n"
        f"  🎯 Практик сдано: <b>{stats.get('hw_attempts', 0)}</b>\n"
        f"  ❌ Не сдал: <b>{stats.get('hw_fails', 0)}</b>\n\n"
        f"📈 <b>Ваш винрейт:</b> <code>{winrate}%</code>"
    )

    await message.answer(profile_text, parse_mode="HTML")


@menu_router.message(F.text == "🌐 Язык")
async def change_language(message: Message):
    from handlers.start import get_language_kb
    await message.answer(
        "Выберите язык / Tilni tanlang:",
        reply_markup=get_language_kb()
    )


@menu_router.message(F.text == "🧹 Сброс памяти")
async def reset_memory(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🧹 Контекст сессии очищен! Вы можете начать с чистого листа.",
        reply_markup=get_main_menu(message.from_user.id)
    )
