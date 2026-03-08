import io
import asyncio
import logging
import fitz  # PyMuPDF
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.states import StudyState
from database import Database
from services.gemini import gemini_service

study_router = Router()
logger = logging.getLogger(__name__)

def parse_pdf_pages(pdf_bytes: bytes) -> list[str]:
    """Blocking function to extract text from all pages of a PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.page_count > 200:
        doc.close()
        raise ValueError(f"Limit exceeded: {doc.page_count} > 200")
    
    pages = []
    for i in range(doc.page_count):
        text = doc[i].get_text()
        pages.append(text)
    doc.close()
    return pages

def get_page_image(pdf_bytes: bytes, page_idx: int) -> bytes | None:
    """Extracts the first image found on a specific page."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_idx]
        images = page.get_images(full=True)
        if images:
            xref = images[0][0]
            base_image = doc.extract_image(xref)
            return base_image.get("image")
    except Exception as e:
        logger.error(f"Error extracting image from PDF page {page_idx}: {e}")
    finally:
        doc.close()
    return None

def get_study_kb():
    """Inline keyboard for navigating PDF pages"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Всё понятно, идем дальше", callback_data="next_page")
    builder.button(text="❓ Не понял, объясни иначе", callback_data="explain_more")
    builder.adjust(1)
    return builder.as_markup()

async def send_pdf_page(message: Message, bot: Bot, state: FSMContext):
    """Core function to extract context, generate ai answers, and send to chat."""
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    pages_text = data.get("pages_text", [])
    pdf_bytes = data.get("pdf_bytes")

    if current_page >= len(pages_text):
        return

    page_text = pages_text[current_page]
    
    # If the page is mostly empty, automatically jump to next
    if len(page_text.strip()) < 50:
        await state.update_data(current_page=current_page + 1)
        return await send_pdf_page(message, bot, state)

    wait_msg = await bot.send_message(message.chat.id, f"📖 Анализирую страницу {current_page + 1}...")

    try:
        # Extract images off the event loop
        img_bytes = await asyncio.to_thread(get_page_image, pdf_bytes, current_page)
        
        # Analyze using Gemini 
        gemini_response = await gemini_service.analyze_theory(page_text, image_bytes=img_bytes)
        
        if not gemini_response:
            await wait_msg.edit_text("❌ Ошибка при запросе к AI. Попробуйте еще раз.")
            return

        text_to_send = f"📄 <b>Страница {current_page + 1}</b>\n\n{gemini_response}"
        
        await wait_msg.delete()

        # Reply with photo if image exists, else text
        if img_bytes:
            image_file = BufferedInputFile(img_bytes, filename=f"page_{current_page}.jpg")
            await bot.send_photo(
                message.chat.id, 
                image_file, 
                caption=text_to_send[:1024], 
                reply_markup=get_study_kb()
            )
        else:
            if len(text_to_send) > 4096:
                text_to_send = text_to_send[:4090] + "..."
            await bot.send_message(message.chat.id, text_to_send, reply_markup=get_study_kb())

    except Exception as e:
        logger.error(f"Error sending pdf page {current_page}: {e}")
        await bot.send_message(message.chat.id, "❌ Произошла ошибка при обработке страницы.")


@study_router.message(StudyState.waiting_for_pdf, F.document)
async def handle_pdf_upload(message: Message, bot: Bot, state: FSMContext):
    if message.document.mime_type != "application/pdf":
        await message.answer("❌ Ошибка: Пожалуйста, отправьте файл в формате PDF.")
        return

    status_msg = await message.answer("📥 Загрузка и анализ PDF-книги...\nПожалуйста, подождите.")

    try:
        file_id = message.document.file_id
        file_info = await bot.get_file(file_id)
        downloaded = await bot.download_file(file_info.file_path)
        pdf_bytes = downloaded.read()

        try:
            pages_text = await asyncio.to_thread(parse_pdf_pages, pdf_bytes)
        except ValueError:
            await status_msg.edit_text("❌ Лимит: максимум 200 страниц.")
            return

        # Prepare FSM tracking dict
        await state.update_data(
            pdf_bytes=pdf_bytes,
            pages_text=pages_text,
            current_page=0
        )
        await state.set_state(StudyState.reading_pdf)
        
        await status_msg.delete()
        
        # Start reading process
        await send_pdf_page(message, bot, state)

    except Exception as e:
        logger.error(f"Error reading PDF: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при чтении PDF. Возможно файл поврежден или слишком большой.")


@study_router.callback_query(StudyState.reading_pdf, F.data == "next_page")
async def on_next_page(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    pages_text = data.get("pages_text", [])
    user_id = callback.from_user.id
    
    current_page += 1
    
    if current_page >= len(pages_text):
        await callback.message.answer("🎉 Книга полностью изучена!")
        await Database.increment_studied_books(user_id)
        await state.clear()
        
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass
    else:
        await state.update_data(current_page=current_page)
        await callback.answer("Загружаю следующую страницу...")
        
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass
            
        await send_pdf_page(callback.message, bot, state)


@study_router.callback_query(StudyState.reading_pdf, F.data == "explain_more")
async def on_explain_more(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    pages_text = data.get("pages_text", [])
    
    if current_page >= len(pages_text):
        await callback.answer()
        return

    page_text = pages_text[current_page]
    
    await callback.answer("Подготовка объяснения...")
    wait_msg = await callback.message.answer("🧠 ИИ подготавливает более простое объяснение...")
    
    prompt = (
        "Пожалуйста, объясни этот материал максимально ПРОСТЫМ языком, "
        "как для полнейшего новичка. Приведи понятные примеры.\n\n"
        f"Материал:\n{page_text}"
    )
    
    try:
        response = await gemini_service.analyze_theory(prompt)
        
        if response:
            if len(response) > 4096:
                response = response[:4090] + "..."
            await wait_msg.edit_text(f"💡 <b>Простое объяснение:</b>\n\n{response}")
        else:
            await wait_msg.edit_text("❌ Ошибка генерации объяснения.")
    except Exception as e:
        logger.error(f"Error on explain_more: {e}")
        await wait_msg.edit_text("❌ Произошла ошибка.")
