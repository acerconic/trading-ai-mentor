import io
import re
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


def _clean_html(text: str) -> str:
    """Convert markdown bold to HTML bold and remove leftover asterisks."""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = text.replace("*", "")
    return text


def parse_pdf_pages(pdf_bytes: bytes) -> list[str]:
    """Extract text from every page of a PDF. No page limit."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i in range(doc.page_count):
        text = doc[i].get_text()
        if len(text.strip()) > 50:
            pages.append(text)
    doc.close()
    if not pages:
        raise ValueError("PDF не содержит извлекаемого текста (возможно, это сканированные изображения).")
    return pages


def get_page_image(pdf_bytes: bytes, page_idx: int) -> bytes | None:
    """Render a PDF page to JPEG at 1.5x zoom."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_idx]
        mat  = fitz.Matrix(1.5, 1.5)
        pix  = page.get_pixmap(matrix=mat)
        return pix.tobytes("jpeg")
    except Exception as e:
        logger.error(f"Error extracting image from page {page_idx}: {e}")
        return None
    finally:
        doc.close()


def get_study_kb() -> InlineKeyboardBuilder:
    """Inline keyboard for navigating PDF pages."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Всё понятно, идем дальше",  callback_data="next_page")
    builder.button(text="📖 Не понял, объясни иначе",   callback_data="explain_more")
    builder.button(text="❓ У меня вопрос (спросить)",  callback_data="ask_question_btn")
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────────────────────
#  Core function: render + analyse + send one PDF page
# ──────────────────────────────────────────────────────────────
async def send_pdf_page(message: Message, bot: Bot, state: FSMContext):
    data         = await state.get_data()
    current_page = data.get("current_page", 0)
    pages_text   = data.get("pages_text", [])
    pdf_bytes    = data.get("pdf_bytes")

    if current_page >= len(pages_text):
        return

    page_text = pages_text[current_page]
    wait_msg  = await bot.send_message(
        message.chat.id,
        f"📖 Анализирую страницу {current_page + 1} из {len(pages_text)}…"
    )

    try:
        # Render page image (non-blocking)
        img_bytes = await asyncio.to_thread(get_page_image, pdf_bytes, current_page)

        # AI explanation
        ai_response = await gemini_service.analyze_theory(page_text)

        if not ai_response:
            await wait_msg.edit_text("❌ Ошибка при запросе к AI. Проверьте API-ключи и попробуйте ещё раз.")
            return

        html_response = _clean_html(ai_response)
        text_to_send  = f"📄 <b>Страница {current_page + 1}</b>\n\n{html_response}"
        if len(text_to_send) > 4096:
            text_to_send = text_to_send[:4090] + "…"

        await wait_msg.delete()

        if img_bytes:
            await bot.send_photo(
                message.chat.id,
                BufferedInputFile(img_bytes, filename=f"page_{current_page}.jpg")
            )

        await bot.send_message(message.chat.id, text_to_send,
                               reply_markup=get_study_kb(), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error sending PDF page {current_page}: {e}", exc_info=True)
        try:
            await wait_msg.edit_text("❌ Произошла ошибка при обработке страницы.")
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
#  UPLOAD handler
# ──────────────────────────────────────────────────────────────
@study_router.message(StudyState.waiting_for_pdf, F.document)
async def handle_pdf_upload(message: Message, bot: Bot, state: FSMContext):
    if message.document.mime_type != "application/pdf":
        await message.answer("❌ Пожалуйста, отправьте файл в формате <b>PDF</b>.", parse_mode="HTML")
        return

    status_msg = await message.answer("📥 Загружаю и анализирую PDF…\n⏳ Это может занять несколько секунд.")

    try:
        file_info  = await bot.get_file(message.document.file_id)
        downloaded = await bot.download_file(file_info.file_path)
        pdf_bytes  = downloaded.read()

        try:
            pages_text = await asyncio.to_thread(parse_pdf_pages, pdf_bytes)
        except ValueError as e:
            await status_msg.edit_text(f"❌ {e}")
            return

        await state.update_data(pdf_bytes=pdf_bytes, pages_text=pages_text, current_page=0)
        await state.set_state(StudyState.reading_pdf)
        await status_msg.delete()
        await send_pdf_page(message, bot, state)

    except Exception as e:
        logger.error(f"Error reading PDF: {e}", exc_info=True)
        await status_msg.edit_text("❌ Ошибка при чтении PDF. Файл может быть повреждён или слишком большим.")


# ──────────────────────────────────────────────────────────────
#  NEXT PAGE
# ──────────────────────────────────────────────────────────────
@study_router.callback_query(StudyState.reading_pdf, F.data == "next_page")
async def on_next_page(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data         = await state.get_data()
    current_page = data.get("current_page", 0) + 1
    pages_text   = data.get("pages_text", [])

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if current_page >= len(pages_text):
        await callback.message.answer("🎉 <b>Книга полностью изучена!</b> Отличная работа!", parse_mode="HTML")
        await Database.increment_studied_books(callback.from_user.id)
        await state.clear()
    else:
        await state.update_data(current_page=current_page)
        await callback.answer("Загружаю следующую страницу…")
        await send_pdf_page(callback.message, bot, state)


# ──────────────────────────────────────────────────────────────
#  EXPLAIN SIMPLER
# ──────────────────────────────────────────────────────────────
@study_router.callback_query(StudyState.reading_pdf, F.data == "explain_more")
async def on_explain_more(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data       = await state.get_data()
    pages_text = data.get("pages_text", [])
    cur        = data.get("current_page", 0)

    if cur >= len(pages_text):
        await callback.answer()
        return

    await callback.answer("Готовлю простое объяснение…")
    wait_msg = await callback.message.answer("🧠 ИИ переформулирует материал простым языком…")

    try:
        response = await gemini_service.explain_simpler(pages_text[cur])
        if response:
            response = _clean_html(response)
            if len(response) > 4000:
                response = response[:4000] + "…"
            await wait_msg.edit_text(
                f"💡 <b>Простое объяснение:</b>\n\n{response}",
                parse_mode="HTML"
            )
        else:
            await wait_msg.edit_text("❌ Не получилось сгенерировать объяснение. Попробуйте ещё раз.")
    except Exception as e:
        logger.error(f"explain_more error: {e}", exc_info=True)
        await wait_msg.edit_text("❌ Произошла ошибка. Попробуйте ещё раз.")


# ──────────────────────────────────────────────────────────────
#  ASK QUESTION — trigger
# ──────────────────────────────────────────────────────────────
@study_router.callback_query(StudyState.reading_pdf, F.data == "ask_question_btn")
async def process_ask_question_btn(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = (data.get("language") or "RU").upper()

    if lang == "UZ":
        prompt_text = "❓ Тушунмаган сўзингиз ёки саволингизни ёзинг (масалан: 'Orderblock нима?'):"
    else:
        prompt_text = "❓ Напишите свой вопрос или термин, который вам непонятен\n(например: <i>'Что такое Ордерблок?'</i>):"

    await callback.message.answer(prompt_text, parse_mode="HTML")
    await state.set_state(StudyState.asking_question)
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  ASK QUESTION — handle the user's text
# ──────────────────────────────────────────────────────────────
@study_router.message(StudyState.asking_question, F.text)
async def process_user_question(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = (data.get("language") or "RU").lower()   # normalize: "RU" → "ru"

    wait_msg = await message.answer("🔍 Ищу ответ…")

    answer = None

    # 1. First try local NLP knowledge base (instant, no API cost)
    try:
        from services.nlp import nlp_service
        answer = nlp_service.get_best_trading_fact(message.text, lang)
        # If NLP only returned the generic "not found" fallback, escalate to AI
        if answer and ("не нашел" in answer or "топилмади" in answer):
            answer = None
    except Exception as e:
        logger.warning(f"NLP lookup failed, falling back to AI: {e}")

    # 2. Fallback to full AI answer if NLP didn't find a good match
    if not answer:
        try:
            answer = await gemini_service.answer_question(message.text)
        except Exception as e:
            logger.error(f"AI answer_question failed: {e}")

    if not answer:
        answer = "💡 Извините, не удалось найти ответ. Попробуйте переформулировать вопрос."

    answer = _clean_html(answer)
    if len(answer) > 4000:
        answer = answer[:4000] + "…"

    try:
        await wait_msg.edit_text(
            f"🤖 <b>AI Ментор:</b>\n\n{answer}",
            parse_mode="HTML"
        )
    except Exception:
        await message.answer(f"🤖 <b>AI Ментор:</b>\n\n{answer}", parse_mode="HTML")

    # Return to reading so the navigation buttons still work
    await state.set_state(StudyState.reading_pdf)
