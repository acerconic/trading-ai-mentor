import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext

from database import Database
from utils.states import StudyState, PracticeState

menu_router = Router()
logger = logging.getLogger(__name__)

def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню бота"""
    kb = [
        [KeyboardButton(text="📚 Новая тема"), KeyboardButton(text="📝 Практика")],
        [KeyboardButton(text="👤 Мой Профиль"), KeyboardButton(text="🌐 Язык")],
        [KeyboardButton(text="🧹 Сброс памяти")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@menu_router.callback_query(F.data.in_(["lang_ru", "lang_uz"]))
async def process_language_selection(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = "RU" if callback.data == "lang_ru" else "UZ"
    
    await Database.update_language(user_id, lang)
    
    # Удаляем инлайн-кнопки
    try:
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения выбора языка: {e}")
        
    await callback.message.answer(
        f"✅ Язык успешно изменен на {lang}!\n\nЧто бы вы хотели сделать далее?",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@menu_router.message(F.text == "📚 Новая тема")
async def start_new_topic(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, отправьте мне PDF-книгу или файл (максимум до 200 страниц) для начала обучения.")
    await state.set_state(StudyState.waiting_for_pdf)

@menu_router.message(F.text == "📝 Практика")
async def start_practice(message: Message, state: FSMContext):
    await message.answer("Пришлите мне скриншот вашего графика (PNG/JPG) с вашим видением рынка (SMC/ICT), и я проверю его.")
    await state.set_state(PracticeState.waiting_for_chart)

@menu_router.message(F.text == "👤 Мой Профиль")
async def show_profile(message: Message):
    user_id = message.from_user.id
    user = await Database.get_user(user_id)
    
    if not user:
        await message.answer("Профиль не найден.")
        return
        
    stats = await Database.get_stats(user_id)
    
    profile_text = (
        f"👤 <b>Профиль Трейдера:</b> @{user['username']}\n"
        f"🌐 <b>Язык:</b> {user['language'] or 'Не выбран'}\n\n"
        f"📊 <b>Статистика обучения:</b>\n"
        f"📚 Изученных тем (книг): {stats.get('studied_books', 0)}\n"
        f"📝 Выполнено Домашних Заданий: {stats.get('hw_attempts', 0)}\n"
        f"❌ Ошибок в ДЗ: {stats.get('hw_fails', 0)}\n\n"
        f"🎯 <b>Ваш Винрейт:</b> <code>{stats.get('winrate', 0.0)}%</code>"
    )
    
    await message.answer(profile_text)

@menu_router.message(F.text == "🧹 Сброс памяти")
async def reset_memory(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🧹 Ок, я забыл контекст текущей сессии! Все состояния очищены.", reply_markup=get_main_menu())
