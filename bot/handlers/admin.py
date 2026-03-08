import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

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
