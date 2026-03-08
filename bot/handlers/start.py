import logging
from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database import Database
from config import ADMIN_ID

start_router = Router()
logger = logging.getLogger(__name__)

def get_main_menu():
    """Главное меню бота"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📚 Новая тема")
    builder.button(text="📝 Практика")
    builder.button(text="👤 Мой Профиль")
    builder.button(text="🌐 Язык")
    builder.button(text="🧹 Сброс памяти")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_language_kb() -> InlineKeyboardMarkup:
    """Инлайн-кнопки выбора языка"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    return builder.as_markup()

@start_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    user = await Database.get_user(user_id)
    
    if not user:
        # Новый юзер - добавляем в БД
        await Database.add_user(user_id, username)
        await message.answer("🔒 Доступ закрыт. Ваша заявка отправлена администратору.")
        
        # Отправляем заявку админу
        admin_kb = InlineKeyboardBuilder()
        admin_kb.button(text="✅ Одобрить", callback_data=f"approve_{user_id}")
        admin_kb.button(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 <b>Новая заявка на доступ:</b>\nПользователь: @{username}\nID: <code>{user_id}</code>",
                reply_markup=admin_kb.as_markup()
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу: {e}")
            
    else:
        # Юзер уже есть в БД
        if not user["is_approved"]:
            await message.answer("Ваша заявка еще на рассмотрении.")
        elif user["language"] is None:
            await message.answer("Пожалуйста, выберите язык / Iltimos, tilni tanlang:", reply_markup=get_language_kb())
        else:
            await message.answer("Добро пожаловать обратно!", reply_markup=get_main_menu())
