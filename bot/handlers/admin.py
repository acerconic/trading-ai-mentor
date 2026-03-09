import logging
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message

from database import Database
from config import ADMIN_ID

admin_router = Router()
logger = logging.getLogger(__name__)

@admin_router.callback_query(F.data.startswith("approve_") | F.data.startswith("reject_"))
async def process_admin_decision(callback: CallbackQuery, bot: Bot):
    # Дополнительная жесткая проверка на ADMIN_ID для безопасности
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    data_parts = callback.data.split("_")
    action = data_parts[0]
    user_id = int(data_parts[1])

    if action == "approve":
        # Обновляем БД
        await Database.update_approval(user_id, is_approved=True)
        
        # Редактируем сообщение админа
        new_text = f"{callback.message.html_text}\n\n✅ <b>Одобрено</b>"
        try:
            await callback.message.edit_text(new_text)
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения админа: {e}")

        # Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=user_id,
                text="🎉 Доступ открыт! Нажмите /start для выбора языка."
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
            
        await callback.answer("Пользователь одобрен!")

    elif action == "reject":
        # Отмечаем отклонение в сообщении админа
        new_text = f"{callback.message.html_text}\n\n❌ <b>Отклонено</b>"
        try:
            await callback.message.edit_text(new_text)
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения админа: {e}")

        # Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=user_id,
                text="❌ Ваша заявка была отклонена администратором."
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
            
        await callback.answer("Пользователь отклонен!")

@admin_router.message(F.text == "/admin")
async def show_admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    users = await Database.get_all_users()
    total_users = len(users)
    approved_users = sum(1 for u in users if u.get("is_approved"))
    
    total_books = sum(u.get("studied_books", 0) for u in users)
    total_hw = sum(u.get("hw_attempts", 0) for u in users)
    
    msg = (
        "👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n\n"
        f"📊 <b>Общая статистика:</b>\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ Одобренных учеников: <b>{approved_users}</b>\n"
        f"📚 Изучено книг (всеми): <b>{total_books}</b>\n"
        f"🎯 Сдано практик: <b>{total_hw}</b>\n\n"
        f"💡 <i>Лимиты на размер книг (страниц/МБ) отключены для всех одобренных пользователей!</i>\n"
    )
    
    # Можно добавить список топ учеников
    top_students = sorted([u for u in users if u.get("is_approved")], key=lambda x: x.get("studied_books", 0), reverse=True)[:5]
    if top_students:
        msg += "\n🏆 <b>Топ-5 учеников (книги):</b>\n"
        for i, u in enumerate(top_students, 1):
            msg += f"{i}. {u.get('username') or 'Без имени'} (ID: {u.get('telegram_id')}) - <b>{u.get('studied_books')} книг</b>\n"
            
    await message.answer(msg)
