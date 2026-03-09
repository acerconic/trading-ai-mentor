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
    """
    Anti-spam protection.
    Rules:
      - Admin          → always bypassed
      - Approved users → always bypassed (admin trusted them manually)
      - Unknown/new/unapproved users → 5-sec cooldown
      - /start command → always bypassed (needed for onboarding)
    """
    def __init__(self, limit: float = 5.0):
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

        # 1. Admin — no throttle
        if str(user_id) == str(ADMIN_ID):
            return await handler(event, data)

        # 2. /start — no throttle (required for onboarding flow)
        if event.text and event.text.startswith("/start"):
            return await handler(event, data)

        # 3. Approved users — no throttle (admin already trusted them)
        user = await Database.get_user(user_id)
        if user and user.get("is_approved"):
            return await handler(event, data)

        # 4. Unknown / unapproved users — apply cooldown
        now = time.time()
        last = self.user_timers.get(user_id, 0.0)
        elapsed = now - last

        if elapsed < self.limit:
            wait = int(self.limit - elapsed)
            lang = (user.get("language") or "ru").lower() if user else "ru"
            if lang not in TRADING_FACTS:
                lang = "ru"

            fact = random.choice(TRADING_FACTS[lang])

            if lang == "uz":
                msg = (
                    f"⏳ <b>Anti-spam!</b> Iltimos, {wait} soniya kuting.\n\n"
                    f"<i>Kutish vaqtida qiziqarli fakt:</i>\n{fact}"
                )
            else:
                msg = (
                    f"⏳ <b>Анти-спам!</b> Пожалуйста, подождите {wait} сек.\n\n"
                    f"<i>А пока вот интересный факт:</i>\n{fact}"
                )

            await event.answer(msg, parse_mode="HTML")
            return

        result = await handler(event, data)
        self.user_timers[user_id] = time.time()
        return result
