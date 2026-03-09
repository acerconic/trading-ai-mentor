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


# ────────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────────

def _clean_html(text: str) -> str:
    """Convert markdown bold to HTML bold and strip leftover asterisks."""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = text.replace("*", "")
    return text


def _truncate(text: str, limit: int = 4000) -> str:
    return text[:limit] + "…" if len(text) > limit else text


def parse_pdf_pages(pdf_bytes: bytes) -> list[str]:
    """
    Extract text from every page of a PDF.
    Returns an empty list if the PDF appears to be scanned (image-only).
    No page limit.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i in range(doc.page_count):
        text = doc[i].get_text().strip()
        if len(text) > 50:
            pages.append(text)
    doc.close()
    return pages  # empty list = scanned PDF


def get_page_count(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    n = doc.page_count
    doc.close()
    return n


def get_page_image(pdf_bytes: bytes, page_idx: int) -> bytes | None:
    """Render a PDF page to JPEG at 1.5× zoom."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        mat = fitz.Matrix(1.5, 1.5)
        pix = doc[page_idx].get_pixmap(matrix=mat)
        return pix.tobytes("jpeg")
    except Exception as e:
        logger.error(f"Error rendering page {page_idx}: {e}")
        return None
    finally:
        doc.close()


def get_study_kb() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Всё понятно, идём дальше",  callback_data="next_page")
    builder.button(text="📖 Не понял, объясни иначе",   callback_data="explain_more")
    builder.button(text="❓ У меня вопрос (спросить)",  callback_data="ask_question_btn")
    builder.adjust(1)
    return builder.as_markup()


# ────────────────────────────────────────────────────────────────────────
#  CORE: send one page (supports both text-PDF and scanned-PDF)
# ────────────────────────────────────────────────────────────────────────

async def send_pdf_page(message: Message, bot: Bot, state: FSMContext):
    data         = await state.get_data()
    current_page = data.get("current_page", 0)
    pages_text   = data.get("pages_text", [])
    pdf_bytes    = data.get("pdf_bytes")
    total_pages  = data.get("total_pages", len(pages_text))
    is_scanned   = data.get("is_scanned", False)

    if is_scanned:
        # Scanned PDF: use page index directly
        if current_page >= total_pages:
            return
    else:
        if current_page >= len(pages_text):
            return

    wait_msg = await bot.send_message(
        message.chat.id,
        f"📖 Анализирую страницу {current_page + 1} из {total_pages}…"
    )

    try:
        img_bytes = await asyncio.to_thread(get_page_image, pdf_bytes, current_page)

        if is_scanned:
            # ── SCANNED PDF: Gemini reads the image and explains it ──
            ai_response = await gemini_service.read_scanned_page(img_bytes, current_page + 1)
        else:
            # ── NORMAL PDF: text → text-only LLM ──
            page_text   = pages_text[current_page]
            ai_response = await gemini_service.analyze_theory(page_text)

        if not ai_response:
            await wait_msg.edit_text(
                "❌ Ошибка при запросе к AI. Проверьте API-ключи и попробуйте ещё раз."
            )
            return

        html = _clean_html(ai_response)
        text_to_send = _truncate(f"📄 <b>Страница {current_page + 1}</b>\n\n{html}")

        await wait_msg.delete()

        if img_bytes:
            await bot.send_photo(
                message.chat.id,
                BufferedInputFile(img_bytes, filename=f"page_{current_page}.jpg")
            )

        await bot.send_message(
            message.chat.id, text_to_send,
            reply_markup=get_study_kb(), parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in send_pdf_page (page {current_page}): {e}", exc_info=True)
        try:
            await wait_msg.edit_text("❌ Произошла ошибка при обработке страницы. Попробуйте ещё раз.")
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────────────
#  UPLOAD HANDLER
# ────────────────────────────────────────────────────────────────────────

@study_router.message(StudyState.waiting_for_pdf, F.document)
async def handle_pdf_upload(message: Message, bot: Bot, state: FSMContext):
    if message.document.mime_type != "application/pdf":
        await message.answer("❌ Пожалуйста, отправьте файл в формате <b>PDF</b>.", parse_mode="HTML")
        return

    status_msg = await message.answer(
        "📥 Загружаю PDF…\n⏳ Определяю тип документа (текст или скан)."
    )

    try:
        file_info  = await bot.get_file(message.document.file_id)
        downloaded = await bot.download_file(file_info.file_path)
        pdf_bytes  = downloaded.read()

        # Attempt text extraction
        pages_text   = await asyncio.to_thread(parse_pdf_pages, pdf_bytes)
        total_pages  = await asyncio.to_thread(get_page_count, pdf_bytes)
        is_scanned   = len(pages_text) == 0

        if is_scanned and not __import__("config").OPENROUTER_API_KEY:
            await status_msg.edit_text(
                "❌ Этот PDF содержит только сканированные изображения.\n\n"
                "Для чтения сканов нужен <b>OPENROUTER_API_KEY</b>.\n"
                "Получите его бесплатно на <a href='https://openrouter.ai'>openrouter.ai</a> "
                "и добавьте в Render → Environment.",
                parse_mode="HTML"
            )
            return

        if is_scanned:
            mode_text = f"📡 Обнаружен <b>сканированный PDF</b> ({total_pages} стр.).\n🤖 Читаю через Vision AI (OpenRouter)…"
        else:
            mode_text = f"📄 Обнаружен текстовый PDF: <b>{len(pages_text)} стр. с теорией</b>."

        await status_msg.edit_text(mode_text, parse_mode="HTML")

        await state.update_data(
            pdf_bytes=pdf_bytes,
            pages_text=pages_text,
            current_page=0,
            total_pages=total_pages,
            is_scanned=is_scanned,
        )
        await state.set_state(StudyState.reading_pdf)

        await asyncio.sleep(1)
        await status_msg.delete()
        await send_pdf_page(message, bot, state)

    except Exception as e:
        logger.error(f"Error reading PDF: {e}", exc_info=True)
        await status_msg.edit_text(
            "❌ Ошибка при чтении PDF. Файл может быть повреждён или зашифрован."
        )


# ────────────────────────────────────────────────────────────────────────
#  NEXT PAGE
# ────────────────────────────────────────────────────────────────────────

@study_router.callback_query(StudyState.reading_pdf, F.data == "next_page")
async def on_next_page(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data         = await state.get_data()
    current_page = data.get("current_page", 0) + 1
    pages_text   = data.get("pages_text", [])
    total_pages  = data.get("total_pages", len(pages_text))
    is_scanned   = data.get("is_scanned", False)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    end_reached = current_page >= (total_pages if is_scanned else len(pages_text))

    if end_reached:
        await callback.message.answer(
            "🎉 <b>Книга полностью изучена!</b> Отличная работа! 🏆",
            parse_mode="HTML"
        )
        await Database.increment_studied_books(callback.from_user.id)
        await state.clear()
    else:
        await state.update_data(current_page=current_page)
        await callback.answer("Загружаю следующую страницу…")
        await send_pdf_page(callback.message, bot, state)


# ────────────────────────────────────────────────────────────────────────
#  EXPLAIN SIMPLER
# ────────────────────────────────────────────────────────────────────────

@study_router.callback_query(StudyState.reading_pdf, F.data == "explain_more")
async def on_explain_more(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data       = await state.get_data()
    pages_text = data.get("pages_text", [])
    cur        = data.get("current_page", 0)
    is_scanned = data.get("is_scanned", False)

    await callback.answer("Готовлю простое объяснение…")
    wait_msg = await callback.message.answer("🧠 ИИ переформулирует материал простым языком…")

    try:
        if is_scanned:
            # For scanned PDFs re-render the same page and ask Vision AI to simplify
            pdf_bytes = data.get("pdf_bytes")
            img_bytes = await asyncio.to_thread(get_page_image, pdf_bytes, cur)
            prompt = (
                "Ты терпеливый ментор по трейдингу. Объясни содержимое этой страницы "
                "максимально ПРОСТЫМ языком для абсолютного новичка. "
                "Используй жизненные аналогии, эмодзи и структуру."
            )
            response = await gemini_service.read_scanned_page(img_bytes, cur + 1)
        else:
            if cur >= len(pages_text):
                await callback.answer()
                return
            response = await gemini_service.explain_simpler(pages_text[cur])

        if response:
            response = _clean_html(response)
            await wait_msg.edit_text(
                _truncate(f"💡 <b>Простое объяснение:</b>\n\n{response}"),
                parse_mode="HTML"
            )
        else:
            await wait_msg.edit_text("❌ Не получилось сгенерировать объяснение. Попробуйте ещё раз.")

    except Exception as e:
        logger.error(f"explain_more error: {e}", exc_info=True)
        await wait_msg.edit_text("❌ Произошла ошибка. Попробуйте ещё раз.")


# ────────────────────────────────────────────────────────────────────────
#  ASK QUESTION — trigger
# ────────────────────────────────────────────────────────────────────────

@study_router.callback_query(StudyState.reading_pdf, F.data == "ask_question_btn")
async def process_ask_question_btn(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = (data.get("language") or "RU").upper()

    if lang == "UZ":
        prompt_text = "❓ Тушунмаган сўзингиз ёки саволингизни ёзинг (масалан: 'Orderblock нима?'):"
    else:
        prompt_text = "❓ Напишите свой вопрос или термин, который вам непонятен\n<i>(например: «Что такое Ордерблок?»)</i>:"

    await callback.message.answer(prompt_text, parse_mode="HTML")
    await state.set_state(StudyState.asking_question)
    await callback.answer()


# ────────────────────────────────────────────────────────────────────────
#  ASK QUESTION — handle answer
# ────────────────────────────────────────────────────────────────────────

@study_router.message(StudyState.asking_question, F.text)
async def process_user_question(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = (data.get("language") or "RU").lower()   # "RU" → "ru"

    wait_msg = await message.answer("🔍 Ищу ответ…")
    answer   = None

    # 1. Local NLP knowledge base (instant)
    try:
        from services.nlp import nlp_service
        candidate = nlp_service.get_best_trading_fact(message.text, lang)
        # Only use NLP result if it seems relevant (not the generic fallback)
        if candidate and "не нашел" not in candidate and "топилмади" not in candidate:
            answer = candidate
    except Exception as e:
        logger.warning(f"NLP failed, escalating to AI: {e}")

    # 2. AI fallback (if NLP had no good match)
    if not answer:
        try:
            answer = await gemini_service.answer_question(message.text)
        except Exception as e:
            logger.error(f"answer_question failed: {e}")

    if not answer:
        answer = "💡 Не удалось найти ответ. Попробуйте переформулировать вопрос."

    try:
        await wait_msg.edit_text(
            _truncate(f"🤖 <b>AI Ментор:</b>\n\n{_clean_html(answer)}"),
            parse_mode="HTML"
        )
    except Exception:
        await message.answer(
            _truncate(f"🤖 <b>AI Ментор:</b>\n\n{_clean_html(answer)}"),
            parse_mode="HTML"
        )

    await state.set_state(StudyState.reading_pdf)
