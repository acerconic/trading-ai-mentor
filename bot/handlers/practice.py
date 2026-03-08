import io
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.states import PracticeState
from database import Database
from services.gemini import gemini_service

practice_router = Router()
logger = logging.getLogger(__name__)

@practice_router.message(PracticeState.waiting_for_chart, F.photo | F.document)
async def handle_homework_chart(message: Message, bot: Bot, state: FSMContext):
    user_id = message.from_user.id
    
    file_id = None
    if message.photo:
        # Taking the highest resolution photo
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
        file_id = message.document.file_id
    else:
        await message.answer("❌ Пожалуйста, отправьте изображение (PNG или JPG).")
        return

    status_msg = await message.answer("🧠 Нейросеть анализирует ваш график...\n⏳ Пожалуйста, подождите.")

    try:
        file_info = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        img_bytes = downloaded_file.read()

        caption = message.caption or ""
        
        gemini_response = await gemini_service.analyze_homework(image_bytes=img_bytes, prompt_text=caption)
        
        if not gemini_response:
            await status_msg.edit_text("❌ Ошибка при обращении к нейросети. API не отвечает или перегружен.")
            return

        # Check for failure markers
        response_lower = gemini_response.lower()
        is_failed = any(marker in response_lower for marker in ["не сдал", "ошибка", "fail", "не правильн"])
        
        await Database.record_hw_attempt(user_id, failed=is_failed)
        
        # Display response to user
        await status_msg.edit_text(f"📊 <b>Результат проверки:</b>\n\n{gemini_response}")
        
        # Clear state
        await state.clear()

    except Exception as e:
        logger.error(f"Error analyzing homework for {user_id}: {e}")
        await status_msg.edit_text("❌ Произошла непредвиденная ошибка при проверке графика. Убедитесь, что отправили корректное изображение.")
