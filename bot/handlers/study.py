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
from utils.i18n import t
from database import Database
from services.gemini import gemini_service

study_router = Router()
logger = logging.getLogger(__name__)


def _truncate(text: str, limit: int = 4000) -> str:
    return text[:limit] + "…" if len(text) > limit else text


def parse_pdf_pages(pdf_bytes: bytes) -> list[str]:
    doc   = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [doc[i].get_text().strip() for i in range(doc.page_count)]
    doc.close()
    return [p for p in pages if len(p) > 50]


def get_page_count(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    n   = doc.page_count
    doc.close()
    return n


def get_page_image(pdf_bytes: bytes, page_idx: int, max_side: int = 1024) -> bytes | None:
    """Render page → compress to ≤1024px JPEG (~150-300 KB)."""
    from PIL import Image
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            img   = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        result = buf.getvalue()
        logger.info(f"Page {page_idx} image: {len(result) // 1024} KB")
        return result
    except Exception as e:
        logger.error(f"Page render error {page_idx}: {e}", exc_info=True)
        return None
    finally:
        doc.close()


def get_study_kb(lang: str = "RU") -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_next_page",    lang), callback_data="next_page")
    builder.button(text=t("btn_explain_more", lang), callback_data="explain_more")
    builder.button(text=t("btn_ask_question", lang), callback_data="ask_question_btn")
    builder.adjust(1)
    return builder.as_markup()


# ────────────────────────────────────────────────────────────────────────
#  Core: render + AI + send one page
# ────────────────────────────────────────────────────────────────────────

async def send_pdf_page(message: Message, bot: Bot, state: FSMContext):
    data         = await state.get_data()
    cur          = data.get("current_page", 0)
    pages_text   = data.get("pages_text", [])
    pdf_bytes    = data.get("pdf_bytes")
    total        = data.get("total_pages", len(pages_text))
    is_scanned   = data.get("is_scanned", False)
    lang         = (data.get("language") or "RU").upper()

    wait_msg = await bot.send_message(
        message.chat.id,
        t("page_analysing", lang).format(cur=cur + 1, total=total)
    )

    try:
        img_bytes = await asyncio.to_thread(get_page_image, pdf_bytes, cur)

        if is_scanned:
            ai_response = await gemini_service.read_scanned_page(img_bytes, cur + 1, lang)
        else:
            ai_response = await gemini_service.analyze_theory(pages_text[cur], lang)

        if not ai_response:
            await wait_msg.edit_text(t("page_ai_error", lang))
            return

        page_label   = t("page_label", lang).format(n=cur + 1)
        text_to_send = _truncate(f"{page_label}\n\n{ai_response}")

        await wait_msg.delete()

        if img_bytes:
            await bot.send_photo(
                message.chat.id,
                BufferedInputFile(img_bytes, filename=f"page_{cur}.jpg")
            )

        await bot.send_message(
            message.chat.id, text_to_send,
            reply_markup=get_study_kb(lang), parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"send_pdf_page error (page {cur}): {e}", exc_info=True)
        try:
            await wait_msg.edit_text(t("page_error", lang))
        except Exception:
            pass


# ────────────────────────────────────────────────────────────────────────
#  Upload
# ────────────────────────────────────────────────────────────────────────

@study_router.message(StudyState.waiting_for_pdf, F.document)
async def handle_pdf_upload(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    lang = (data.get("language") or "RU").upper()

    if message.document.mime_type != "application/pdf":
        await message.answer(t("send_image_only", lang), parse_mode="HTML")
        return

    status_msg = await message.answer(t("pdf_loading", lang), parse_mode="HTML")

    try:
        file_info  = await bot.get_file(message.document.file_id)
        downloaded = await bot.download_file(file_info.file_path)
        pdf_bytes  = downloaded.read()

        pages_text  = await asyncio.to_thread(parse_pdf_pages, pdf_bytes)
        total_pages = await asyncio.to_thread(get_page_count, pdf_bytes)
        is_scanned  = len(pages_text) == 0

        if is_scanned and not __import__("config").OPENROUTER_API_KEY:
            await status_msg.edit_text(t("pdf_no_openrouter", lang), parse_mode="HTML")
            return

        if is_scanned:
            mode_text = t("pdf_scanned_detected", lang).format(n=total_pages)
        else:
            mode_text = t("pdf_text_detected", lang).format(n=len(pages_text))

        await status_msg.edit_text(mode_text, parse_mode="HTML")

        await state.update_data(
            pdf_bytes=pdf_bytes, pages_text=pages_text,
            current_page=0, total_pages=total_pages, is_scanned=is_scanned,
        )
        await state.set_state(StudyState.reading_pdf)
        await asyncio.sleep(1)
        await status_msg.delete()
        await send_pdf_page(message, bot, state)

    except Exception as e:
        logger.error(f"PDF upload error: {e}", exc_info=True)
        await status_msg.edit_text(t("pdf_corrupted", lang))


# ────────────────────────────────────────────────────────────────────────
#  Next page
# ────────────────────────────────────────────────────────────────────────

@study_router.callback_query(StudyState.reading_pdf, F.data == "next_page")
async def on_next_page(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data        = await state.get_data()
    lang        = (data.get("language") or "RU").upper()
    cur         = data.get("current_page", 0) + 1
    pages_text  = data.get("pages_text", [])
    total       = data.get("total_pages", len(pages_text))
    is_scanned  = data.get("is_scanned", False)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if cur >= (total if is_scanned else len(pages_text)):
        await callback.message.answer(t("book_finished", lang), parse_mode="HTML")
        await Database.increment_studied_books(callback.from_user.id)
        await state.clear()
    else:
        await state.update_data(current_page=cur)
        await callback.answer()
        await send_pdf_page(callback.message, bot, state)


# ────────────────────────────────────────────────────────────────────────
#  Explain simpler
# ────────────────────────────────────────────────────────────────────────

@study_router.callback_query(StudyState.reading_pdf, F.data == "explain_more")
async def on_explain_more(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data       = await state.get_data()
    lang       = (data.get("language") or "RU").upper()
    pages_text = data.get("pages_text", [])
    cur        = data.get("current_page", 0)
    is_scanned = data.get("is_scanned", False)

    await callback.answer()
    wait_msg = await callback.message.answer(t("explain_more_wait", lang))

    try:
        if is_scanned:
            img  = await asyncio.to_thread(get_page_image, data.get("pdf_bytes"), cur)
            resp = await gemini_service.read_scanned_page(img, cur + 1, lang)
        else:
            resp = await gemini_service.explain_simpler(pages_text[cur], lang) if cur < len(pages_text) else None

        if resp:
            prefix = t("explain_more_result", lang)
            await wait_msg.edit_text(
                _truncate(f"{prefix}\n\n{resp}"),
                parse_mode="HTML"
            )
        else:
            await wait_msg.edit_text(t("explain_more_error", lang))

    except Exception as e:
        logger.error(f"explain_more error: {e}", exc_info=True)
        await wait_msg.edit_text(t("explain_more_error", lang))


# ────────────────────────────────────────────────────────────────────────
#  Ask question — trigger
# ────────────────────────────────────────────────────────────────────────

@study_router.callback_query(StudyState.reading_pdf, F.data == "ask_question_btn")
async def process_ask_question_btn(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = (data.get("language") or "RU").upper()
    await callback.message.answer(t("ask_question_prompt", lang), parse_mode="HTML")
    await state.set_state(StudyState.asking_question)
    await callback.answer()


# ────────────────────────────────────────────────────────────────────────
#  Ask question — answer
# ────────────────────────────────────────────────────────────────────────

@study_router.message(StudyState.asking_question, F.text)
async def process_user_question(message: Message, state: FSMContext):
    data     = await state.get_data()
    lang     = (data.get("language") or "RU").upper()
    wait_msg = await message.answer(t("answer_searching", lang))
    answer   = None

    # 1. Local NLP first
    try:
        from services.nlp import nlp_service
        candidate = nlp_service.get_best_trading_fact(message.text, lang.lower())
        if candidate and "не нашел" not in candidate and "топилмади" not in candidate:
            answer = candidate
    except Exception as e:
        logger.warning(f"NLP failed: {e}")

    # 2. AI fallback
    if not answer:
        try:
            answer = await gemini_service.answer_question(message.text, lang)
        except Exception as e:
            logger.error(f"answer_question failed: {e}")

    if not answer:
        answer = t("answer_not_found", lang)

    prefix = t("answer_prefix", lang)
    try:
        await wait_msg.edit_text(
            _truncate(f"{prefix}\n\n{answer}"),
            parse_mode="HTML"
        )
    except Exception:
        await message.answer(_truncate(f"{prefix}\n\n{answer}"), parse_mode="HTML")

    await state.set_state(StudyState.reading_pdf)
