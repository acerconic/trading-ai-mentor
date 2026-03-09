import base64
import asyncio
import logging
import httpx
from openai import AsyncOpenAI
from config import (
    GROQ_API_KEY, CEREBRAS_API_KEY, TOGETHER_API_KEY,
    OPENROUTER_API_KEY, SAMBANOVA_API_KEY, MISTRAL_API_KEY,
    HYPERBOLIC_API_KEY, NOVITA_API_KEY,
)

logger = logging.getLogger(__name__)

HTTPX_TIMEOUT = 90  # seconds

# ─────────────────────────────────────────────────────────────────────────
#  VISION via OpenRouter (FREE vision models — no Gemini key needed)
# ─────────────────────────────────────────────────────────────────────────
# These models support image input on OpenRouter for FREE:
VISION_MODELS = [
    "google/gemini-2.0-flash-exp:free",   # Gemini 2.0 Flash (free tier)
    "qwen/qwen2.5-vl-72b-instruct:free",  # Qwen Vision 72B (free)
    "meta-llama/llama-4-scout:free",       # Llama 4 Scout with vision
]


async def _call_vision(image_bytes: bytes, prompt: str) -> str | None:
    """
    Sends an image + prompt to OpenRouter vision models.
    Tries each free vision model in order until one succeeds.
    """
    if not OPENROUTER_API_KEY:
        return None

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload_content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        {"type": "text", "text": prompt},
    ]

    for model in VISION_MODELS:
        try:
            logger.info(f"→ Vision: trying {model}…")
            async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://trading-ai-mentor.onrender.com",
                        "X-Title": "Trade Mentor Bot",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": payload_content}],
                        "max_tokens": 2048,
                        "temperature": 0.4,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                # Extract text from response
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if text and len(text) > 20:
                    logger.info(f"✅ Vision success via {model}")
                    return text

        except httpx.HTTPStatusError as e:
            logger.warning(f"✗ Vision {model}: HTTP {e.response.status_code} — {e.response.text[:200]}")
        except Exception as e:
            logger.warning(f"✗ Vision {model}: {e}")

    logger.error("All vision models failed.")
    return None


# ─────────────────────────────────────────────────────────────────────────
#  TEXT providers
# ─────────────────────────────────────────────────────────────────────────

class AIManagerService:
    def __init__(self):
        self.clients: dict = {}

        # Priority: fastest + most generous first
        _providers = [
            ("cerebras",   "https://api.cerebras.ai/v1",       CEREBRAS_API_KEY),
            ("groq",       "https://api.groq.com/openai/v1",   GROQ_API_KEY),
            ("sambanova",  "https://api.sambanova.ai/v1",      SAMBANOVA_API_KEY),
            ("hyperbolic", "https://api.hyperbolic.xyz/v1",    HYPERBOLIC_API_KEY),
            ("openrouter", "https://openrouter.ai/api/v1",     OPENROUTER_API_KEY),
            ("together",   "https://api.together.xyz/v1",      TOGETHER_API_KEY),
            ("mistral",    "https://api.mistral.ai/v1",        MISTRAL_API_KEY),
            ("novita",     "https://api.novita.ai/v3/openai",  NOVITA_API_KEY),
        ]
        for name, base_url, key in _providers:
            if key:
                self.clients[name] = AsyncOpenAI(base_url=base_url, api_key=key)
                logger.info(f"✅ Text provider registered: {name}")

        self.text_priority = ["cerebras", "groq", "sambanova", "hyperbolic",
                               "openrouter", "together", "mistral", "novita"]
        self.text_models = {
            "cerebras":   "llama-3.3-70b",
            "groq":       "llama-3.3-70b-versatile",
            "sambanova":  "Meta-Llama-3.3-70B-Instruct",
            "hyperbolic": "meta-llama/Llama-3.3-70B-Instruct",
            "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
            "together":   "meta-llama/Llama-3-70b-chat-hf",
            "mistral":    "mistral-small-latest",
            "novita":     "meta-llama/llama-3.3-70b-instruct",
        }

    async def _text(self, messages: list[dict]) -> str | None:
        if not self.clients:
            logger.error("No text API keys configured!")
            return None

        for provider in self.text_priority:
            if provider not in self.clients:
                continue
            try:
                logger.info(f"→ Text: trying {provider}…")
                resp = await self.clients[provider].chat.completions.create(
                    model=self.text_models[provider],
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.4,
                )
                text = resp.choices[0].message.content
                if text:
                    logger.info(f"✅ Text success via {provider}")
                    return text
            except Exception as e:
                logger.warning(f"✗ {provider}: {e}")

        logger.error("All text providers failed.")
        return None

    # ──────────────────────────────────────────────────────────
    #  1. READ SCANNED PDF PAGE  (OpenRouter Vision → OCR + explain)
    # ──────────────────────────────────────────────────────────
    async def read_scanned_page(self, page_image_bytes: bytes, page_num: int) -> str | None:
        if not OPENROUTER_API_KEY:
            return (
                "⚠️ Для чтения сканированных PDF нужен <b>OPENROUTER_API_KEY</b>.\n"
                "Получите его бесплатно на <a href='https://openrouter.ai'>openrouter.ai</a>."
            )

        prompt = (
            f"Это страница {page_num} из учебника по трейдингу (SMC/ICT). "
            "На скриншоте — отсканированная страница книги.\n\n"
            "Выполни два действия:\n"
            "1. Прочти текст на изображении.\n"
            "2. Объясни этот материал ученику ясно и интересно, как харизматичный ментор по трейдингу. "
            "Используй эмодзи (📊 💡 🎯), жирный текст для терминов, списки для структуры.\n\n"
            "Если на странице нет важной теории (оглавление, пустая страница и т.д.), "
            "скажи: «На этой странице нет важной теории — двигаемся дальше! ➡️»"
        )

        result = await _call_vision(page_image_bytes, prompt)
        if not result:
            return "❌ Не удалось прочитать страницу. Попробуйте ещё раз."
        return result

    # ──────────────────────────────────────────────────────────
    #  2. ANALYSE TRADING CHART  (OpenRouter Vision → feedback)
    # ──────────────────────────────────────────────────────────
    async def analyze_homework(self, image_bytes: bytes, prompt_text: str = "") -> str | None:
        if not OPENROUTER_API_KEY:
            return (
                "⚠️ Для проверки графиков нужен <b>OPENROUTER_API_KEY</b>.\n"
                "Получите его бесплатно на <a href='https://openrouter.ai'>openrouter.ai</a>."
            )

        prompt = (
            "Ты профессиональный ментор по трейдингу в стиле SMC/ICT. "
            "Ученик прислал скриншот своего графика для проверки домашнего задания.\n\n"
            "Что нужно сделать:\n"
            "1. Оцени правильность разметки (Orderblocks, FVG/IFVG, Liquidity, BOS/CHoCH, OTE).\n"
            "2. Укажи конкретные ошибки тактично.\n"
            "3. Дай 1–2 ключевых совета.\n"
            "4. Заверши оценкой: ✅ Принято / ❌ Доработать.\n\n"
            "Формат: структурированный, эмодзи (📊 💡 🎯 📉), тон наставника."
        )
        if prompt_text:
            prompt += f"\n\nВопрос ученика: {prompt_text}"

        result = await _call_vision(image_bytes, prompt)
        if not result:
            return "❌ Не удалось проанализировать график. Убедитесь что OPENROUTER_API_KEY добавлен на Render."
        return result

    # ──────────────────────────────────────────────────────────
    #  3. EXPLAIN PDF PAGE (text)
    # ──────────────────────────────────────────────────────────
    async def analyze_theory(self, page_text: str) -> str | None:
        return await self._text([
            {
                "role": "system",
                "content": (
                    "Ты харизматичный ментор по смарт-мани трейдингу (SMC/ICT). "
                    "Объясни материал ученику максимально доступно и интересно. "
                    "Используй эмодзи (📊 💡 🎯 📉), жирный текст для терминов и списки. "
                    "Общайся как живой наставник. "
                    "Если на странице нет важной теории, скажи: «На этой странице нет важной торговой теории — двигаемся дальше! ➡️»"
                ),
            },
            {"role": "user", "content": f"Текст страницы:\n\n{page_text}"},
        ])

    # ──────────────────────────────────────────────────────────
    #  4. EXPLAIN SIMPLER
    # ──────────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────
    #  5. ANSWER USER QUESTION
    # ──────────────────────────────────────────────────────────
    async def answer_question(self, question: str) -> str | None:
        return await self._text([
            {
                "role": "system",
                "content": (
                    "Ты эксперт по смарт-мани трейдингу (SMC/ICT). "
                    "Дай чёткий, структурированный ответ на вопрос ученика. "
                    "Используй эмодзи, жирный текст и примеры. Кратко и по делу."
                ),
            },
            {"role": "user", "content": question},
        ])


# Singleton
gemini_service = AIManagerService()
