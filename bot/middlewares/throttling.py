import time
import random
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from database import Database
from utils.constants import TRADING_FACTS
from config import ADMIN_ID

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit: float = 30.0):
        self.limit = limit
        self.user_timers: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        if not isinstance(event, Message):
            return await handler(event, data)
            
        user_id = event.from_user.id
        
        # Skip throttling for admin
        if user_id == ADMIN_ID:
            return await handler(event, data)
            
        now = time.time()
        
        last_request_time = self.user_timers.get(user_id, 0.0)
        time_passed = now - last_request_time
        
        if time_passed < self.limit:
            wait_time = int(self.limit - time_passed)
            
            # Fetch user language from database
            user = await Database.get_user(user_id)
            lang = (user.get("language") or "RU").lower() if user else "ru"
            
            # Fallback if language isn't valid
            if lang not in TRADING_FACTS:
                lang = "ru"
            
            fact = random.choice(TRADING_FACTS[lang])
            
            if lang == "ru":
                msg = f"⏳ <b>Анти-спам!</b> Пожалуйста, подождите {wait_time} сек.\n\n<i>А пока вот интересный факт:</i>\n{fact}"
            else:
                msg = f"⏳ <b>Анти-спам!</b> Илтимос, {wait_time} сония кутинг.\n\n<i>Кутиш вақтида қизиқарли факт:</i>\n{fact}"
            
            await event.answer(msg)
            return # Stop processing the message
            
        # If passed the check, execute the handler
        result = await handler(event, data)
        
        # Only update the timer IF the request was successfully processed (non-spam)
        self.user_timers[user_id] = time.time()
        
        return result
