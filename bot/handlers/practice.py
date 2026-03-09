import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.states import PracticeState
from utils.i18n import t
from database import Database
from services.gemini import gemini_service

practice_router = Router()
logger = logging.getLogger(__name__)


@practice_router.message(PracticeState.waiting_for_chart, F.photo | F.document)
async def handle_homework_chart(message: Message, bot: Bot, state: FSMContext):
    data    = await state.get_data()
    lang    = (data.get("language") or "RU").upper()
    user_id = message.from_user.id

    # Accept photo or image document
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif (message.document and message.document.mime_type
          and message.document.mime_type.startswith("image/")):
        file_id = message.document.file_id
    else:
        await message.answer(t("practice_image_only", lang))
        return

    status_msg = await message.answer(t("practice_analysing", lang))

    try:
        file_info      = await bot.get_file(file_id)
        downloaded     = await bot.download_file(file_info.file_path)
        img_bytes      = downloaded.read()
        caption        = message.caption or ""

        response = await gemini_service.analyze_homework(
            image_bytes=img_bytes, prompt_text=caption, lang=lang
        )

        if not response:
            await status_msg.edit_text(t("practice_api_error", lang))
            return

        is_failed = any(m in response.lower()
                        for m in ["доработать", "qayta ishlang", "fail", "❌"])
        await Database.record_hw_attempt(user_id, failed=is_failed)

        header = t("practice_result", lang)
        await status_msg.edit_text(
            f"{header}\n\n{response}",
            parse_mode="HTML"
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Practice error for {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(t("practice_error", lang))
