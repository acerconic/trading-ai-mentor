import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database import Database
from config import ADMIN_ID
from handlers.start import get_main_menu
from utils.states import StudyState, PracticeState
from utils.i18n import t

menu_router = Router()
logger = logging.getLogger(__name__)


async def _get_lang(user_id: int) -> str:
    """Fetch user language from DB, default RU."""
    user = await Database.get_user(user_id)
    return (user.get("language") or "RU").upper() if user else "RU"


# ── Language selection ───────────────────────────────────────────────────────

@menu_router.callback_query(F.data.in_(["lang_ru", "lang_uz"]))
async def process_language_selection(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang    = "RU" if callback.data == "lang_ru" else "UZ"

    await Database.update_language(user_id, lang)

    try:
        await callback.message.delete()
    except Exception:
        pass

    key = "lang_changed_ru" if lang == "RU" else "lang_changed_uz"
    await callback.message.answer(
        t(key, lang),
        reply_markup=get_main_menu(user_id, lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ── New topic ────────────────────────────────────────────────────────────────

@menu_router.message(F.text.in_(["📚 Новая тема", "📚 Yangi mavzu"]))
async def start_new_topic(message: Message, state: FSMContext):
    lang = await _get_lang(message.from_user.id)
    await message.answer(t("send_pdf", lang), parse_mode="HTML")
    await state.update_data(language=lang)
    await state.set_state(StudyState.waiting_for_pdf)


# ── Practice ─────────────────────────────────────────────────────────────────

@menu_router.message(F.text.in_(["📝 Практика", "📝 Amaliyot"]))
async def start_practice(message: Message, state: FSMContext):
    lang = await _get_lang(message.from_user.id)
    await message.answer(t("practice_prompt", lang), parse_mode="HTML")
    await state.update_data(language=lang)
    await state.set_state(PracticeState.waiting_for_chart)


# ── Profile ──────────────────────────────────────────────────────────────────

@menu_router.message(F.text.in_(["👤 Мой Профиль", "👤 Mening Profilim"]))
async def show_profile(message: Message):
    user_id = message.from_user.id
    lang    = await _get_lang(user_id)
    user    = await Database.get_user(user_id)

    if not user:
        await message.answer(t("profile_not_found", lang))
        return

    stats    = await Database.get_stats(user_id)
    winrate  = stats.get("winrate", 0.0)
    books    = stats.get("studied_books", 0)

    if books >= 25:
        rank = t("rank_master", lang)
    elif books >= 15:
        rank = t("rank_trader", lang)
    elif books >= 7:
        rank = t("rank_analyst", lang)
    elif books >= 3:
        rank = t("rank_practitioner", lang)
    else:
        rank = t("rank_beginner", lang)

    lang_display = user["language"] or t("lang_not_set", lang)
    username     = user["username"] or f"user_{user_id}"

    text = (
        f"{t('profile_title', lang)} @{username}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{t('profile_lang', lang)} {lang_display}\n"
        f"{t('profile_rank', lang)} {rank}\n\n"
        f"{t('profile_stats', lang)}\n"
        f"  {t('profile_books', lang)} <b>{books}</b>\n"
        f"  {t('profile_hw', lang)} <b>{stats.get('hw_attempts', 0)}</b>\n"
        f"  {t('profile_fails', lang)} <b>{stats.get('hw_fails', 0)}</b>\n\n"
        f"{t('profile_winrate', lang)} <code>{winrate}%</code>"
    )
    await message.answer(text, parse_mode="HTML")


# ── Language button ───────────────────────────────────────────────────────────

@menu_router.message(F.text.in_(["🌐 Язык", "🌐 Til"]))
async def change_language(message: Message):
    from handlers.start import get_language_kb
    lang = await _get_lang(message.from_user.id)
    await message.answer(t("lang_prompt", lang), reply_markup=get_language_kb())


# ── Reset memory ──────────────────────────────────────────────────────────────

@menu_router.message(F.text.in_(["🧹 Сброс памяти", "🧹 Xotirani tozalash"]))
async def reset_memory(message: Message, state: FSMContext):
    lang = await _get_lang(message.from_user.id)
    await state.clear()
    await message.answer(
        t("reset_done", lang),
        reply_markup=get_main_menu(message.from_user.id, lang),
    )
