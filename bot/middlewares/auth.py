from typing import Any, Awaitable, Callable, Dict
import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from database import Database
from config import ADMIN_ID

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = None
        text = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
            text = event.text
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            text = event.data
            
        if not user_id:
            return await handler(event, data)
            
        # Allow /start command to pass through for onboarding
        if isinstance(event, Message) and text and text.startswith('/start'):
            return await handler(event, data)
            
        # Complete bypass for admins
        if str(user_id) == str(ADMIN_ID):
            return await handler(event, data)
            
        # Allow admin callbacks to pass through
        if isinstance(event, CallbackQuery) and text and (text.startswith('approve_') or text.startswith('reject_')):
            return await handler(event, data)
            
        user = await Database.get_user(user_id)
        
        if not user or not user.get("is_approved"):
            if isinstance(event, Message):
                await event.answer("⛔️ Доступ закрыт. Ваша заявка еще не одобрена или вы не зарегистрированы.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔️ Доступ закрыт.", show_alert=True)
            return # Block execution
            
        return await handler(event, data)
