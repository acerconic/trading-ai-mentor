import base64
import asyncio
import logging
import httpx
from openai import AsyncOpenAI
from config import GROQ_API_KEY, CEREBRAS_API_KEY, TOGETHER_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_TIMEOUT = 60  # seconds


async def _call_gemini_vision(image_bytes: bytes, prompt: str) -> str | None:
    """
    Calls the Gemini REST API directly with httpx.
    This avoids all SDK versioning issues and works reliably.
    """
    if not GEMINI_API_KEY:
        return None

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 2048,
            "temperature": 0.4,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
            resp = await client.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API HTTP error: {e.response.status_code} — {e.response.text}")
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}", exc_info=True)
    return None


class AIManagerService:
    def __init__(self):
        self.clients: dict = {}

        if GROQ_API_KEY:
            self.clients["groq"] = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=GROQ_API_KEY,
            )
        if CEREBRAS_API_KEY:
            self.clients["cerebras"] = AsyncOpenAI(
                base_url="https://api.cerebras.ai/v1",
                api_key=CEREBRAS_API_KEY,
            )
        if TOGETHER_API_KEY:
            self.clients["together"] = AsyncOpenAI(
                base_url="https://api.together.xyz/v1",
                api_key=TOGETHER_API_KEY,
            )

        self.text_priority = ["cerebras", "groq", "together"]
        self.text_models = {
            "cerebras": "llama-3.3-70b",
            "groq":     "llama-3.3-70b-versatile",
            "together": "meta-llama/Llama-3-70b-chat-hf",
        }

    async def _text(self, messages: list[dict]) -> str | None:
        """Try text-only LLM providers in priority order."""
        if not self.clients:
            logger.error("No text API keys configured.")
            return None

        for provider in self.text_priority:
            if provider not in self.clients:
                continue
            try:
                logger.info(f"→ Trying {provider}…")
                resp = await self.clients[provider].chat.completions.create(
                    model=self.text_models[provider],
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.4,
                )
                logger.info(f"✅ Success via {provider}")
                return resp.choices[0].message.content
            except Exception as e:
                logger.warning(f"✗ {provider}: {e}")

        logger.error("All text providers failed.")
        return None

    # ────────────────────────────────────────────────────────────────────
    #  1. READ SCANNED PDF PAGE  (Gemini Vision → extract + explain text)
    # ────────────────────────────────────────────────────────────────────
    async def read_scanned_page(self, page_image_bytes: bytes, page_num: int) -> str | None:
        """
        Sends a scanned PDF page image to Gemini.
        Gemini reads the text from the image AND explains the content.
        Used when the PDF has no extractable machine text.
        """
        prompt = (
            f"Это страница {page_num} из учебника по трейдингу (SMC/ICT). "
            "На изображении — отсканированная страница книги.\n\n"
            "Выполни два действия:\n"
            "1. Прочитай весь текст на изображении (OCR).\n"
            "2. Объясни этот материал ученику доступно и интересно — как харизматичный ментор по трейдингу. "
            "Используй эмодзи (📊 💡 🎯), жирный текст для терминов и списки для структуры.\n\n"
            "Если на странице нет важного торгового материала (оглавление, пустая страница и т.д.), "
            "скажи: «На этой странице нет важной теории — двигаемся дальше! ➡️»"
        )
        result = await _call_gemini_vision(page_image_bytes, prompt)
        if not result and not GEMINI_API_KEY:
            return (
                "⚠️ PDF содержит только сканированные изображения. "
                "Для чтения таких файлов нужен <b>GEMINI_API_KEY</b>.\n\n"
                "Получите его бесплатно на <a href='https://aistudio.google.com/'>aistudio.google.com</a>"
            )
        return result

    # ────────────────────────────────────────────────────────────────────
    #  2. ANALYSE TRADING CHART  (Gemini Vision → homework check)
    # ────────────────────────────────────────────────────────────────────
    async def analyze_homework(self, image_bytes: bytes, prompt_text: str = "") -> str | None:
        if not GEMINI_API_KEY:
            return (
                "⚠️ Для проверки графиков нужен <b>GEMINI_API_KEY</b>.\n\n"
                "Получите его бесплатно на "
                "<a href='https://aistudio.google.com/'>aistudio.google.com</a> "
                "и добавьте в переменные окружения на Render."
            )

        prompt = (
            "Ты профессиональный ментор по трейдингу в стиле SMC/ICT. "
            "Ученик прислал скриншот своего графика для проверки домашнего задания.\n\n"
            "Что нужно сделать:\n"
            "1. Оцени правильность разметки (Orderblocks, FVG/IFVG, Liquidity, BOS/CHoCH, OTE).\n"
            "2. Укажи конкретные ошибки тактично.\n"
            "3. Дай 1–2 ключевых совета по улучшению.\n"
            "4. Заверши оценкой: ✅ Принято / ❌ Доработать.\n\n"
            "Формат: структурированный, с эмодзи (📊 💡 🎯 📉), тон наставника."
        )
        if prompt_text:
            prompt += f"\n\nВопрос ученика к этому графику: {prompt_text}"

        result = await _call_gemini_vision(image_bytes, prompt)
        if not result:
            return "❌ При анализе графика произошла ошибка. Проверьте GEMINI_API_KEY и попробуйте снова."
        return result

    # ────────────────────────────────────────────────────────────────────
    #  3. EXPLAIN PDF TEXT PAGE  (text-only LLMs)
    # ────────────────────────────────────────────────────────────────────
    async def analyze_theory(self, page_text: str) -> str | None:
        return await self._text([
            {
                "role": "system",
                "content": (
                    "Ты харизматичный ментор по смарт-мани трейдингу (SMC/ICT). "
                    "Объясни материал ученику максимально доступно и интересно. "
                    "Используй эмодзи (📊 💡 🎯 📉), жирный текст для терминов и списки. "
                    "Общайся как живой наставник, а не как робот. "
                    "Если на странице нет важной теории — скажи: «На этой странице нет важной торговой теории — двигаемся дальше! ➡️»"
                ),
            },
            {"role": "user", "content": f"Текст страницы:\n\n{page_text}"},
        ])

    # ────────────────────────────────────────────────────────────────────
    #  4. EXPLAIN SIMPLER
    # ────────────────────────────────────────────────────────────────────
    async def explain_simpler(self, page_text: str) -> str | None:
        return await self._text([
            {
                "role": "system",
                "content": (
                    "Ты терпеливый ментор по трейдингу. Ученик не понял материал. "
                    "Объясни тот же материал максимально ПРОСТЫМ языком, как для абсолютного новичка. "
                    "Используй жизненные аналогии, эмодзи и структуру."
                ),
            },
            {"role": "user", "content": f"Объясни попроще:\n\n{page_text}"},
        ])

    # ────────────────────────────────────────────────────────────────────
    #  5. ANSWER USER QUESTION
    # ────────────────────────────────────────────────────────────────────
    async def answer_question(self, question: str) -> str | None:
        return await self._text([
            {
                "role": "system",
                "content": (
                    "Ты эксперт по смарт-мани трейдингу (SMC/ICT). "
                    "Дай чёткий, структурированный ответ на вопрос ученика. "
                    "Используй эмодзи, жирный текст и примеры. Отвечай кратко и по делу."
                ),
            },
            {"role": "user", "content": question},
        ])


# Singleton
gemini_service = AIManagerService()
