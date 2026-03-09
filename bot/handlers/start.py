import logging
from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database import Database
from config import ADMIN_ID
from utils.i18n import t

start_router = Router()
logger = logging.getLogger(__name__)


def get_main_menu(user_id: int = 0, lang: str = "RU"):
    """
    Main menu keyboard. Admin panel button visible only to the admin.
    All button labels are translated to the current language.
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text=t("btn_new_topic", lang))
    builder.button(text=t("btn_practice",  lang))
    builder.button(text=t("btn_profile",   lang))
    builder.button(text=t("btn_language",  lang))
    builder.button(text=t("btn_reset",     lang))
    if user_id == ADMIN_ID:
        builder.button(text=t("btn_admin", lang))
        builder.adjust(2, 2, 1, 1)
    else:
        builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский",    callback_data="lang_ru")
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    return builder.as_markup()


@start_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id  = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"

    user = await Database.get_user(user_id)

    if not user:
        if str(user_id) == str(ADMIN_ID):
            await Database.add_user(user_id, username)
            await Database.update_approval(user_id, is_approved=True)
            await message.answer(t("welcome_admin", "RU"), reply_markup=get_language_kb())
            return

        await Database.add_user(user_id, username)
        await message.answer(t("access_denied", "RU"))

        admin_kb = InlineKeyboardBuilder()
        admin_kb.button(text="✅ Одобрить",  callback_data=f"approve_{user_id}")
        admin_kb.button(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🔔 <b>Новая заявка на доступ:</b>\n"
                    f"Пользователь: @{username}\n"
                    f"ID: <code>{user_id}</code>"
                ),
                reply_markup=admin_kb.as_markup(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Could not notify admin: {e}")
    else:
        lang = (user.get("language") or "RU").upper()

        if str(user_id) == str(ADMIN_ID) and not user["is_approved"]:
            await Database.update_approval(user_id, is_approved=True)
            await message.answer(t("admin_restored", lang), reply_markup=get_language_kb())
            return

        if not user["is_approved"]:
            await message.answer(t("pending_approval", lang))
        elif user["language"] is None:
            await message.answer(t("choose_language", "RU"), reply_markup=get_language_kb())
        else:
            await message.answer(
                t("welcome_back", lang),
                reply_markup=get_main_menu(user_id, lang),
            )
