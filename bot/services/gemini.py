"""
AI service layer.
Vision  → OpenRouter free vision models (NO Google/Gemini)
Text    → Groq, SambaNova, Hyperbolic, OpenRouter DeepSeek V3
Auto-fallback: if one provider's tokens are exhausted → uses the next one.
"""
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
#  VISION MODELS — free, NO Google, ordered by quality
# Confirmed FREE vision models on OpenRouter (no Google, tested as of 2025):
VISION_MODELS = [
    "qwen/qwen2.5-vl-72b-instruct:free",      # Qwen VL 72B — best free vision
    "qwen/qwen2-vl-7b-instruct:free",          # Qwen VL 7B — fast fallback
    "mistralai/pixtral-12b:free",              # Pixtral 12B — Mistral vision
    "microsoft/phi-4-multimodal-instruct:free", # Phi-4 Multimodal — Microsoft
]

# ─────────────────────────────────────────────────────────────────────────
#  TEXT MODELS — most generous free tiers, ordered by speed + quality
# ─────────────────────────────────────────────────────────────────────────
TEXT_MODELS_ON_OPENROUTER = [
    "deepseek/deepseek-chat-v3-0324:free",       # DeepSeek V3 — 64k ctx, very generous
    "meta-llama/llama-4-maverick:free",           # Llama 4 Maverick — huge ctx, top quality
    "meta-llama/llama-3.3-70b-instruct:free",    # Llama 3.3 70B — solid fallback
]


async def _call_vision(image_bytes: bytes, prompt: str) -> str | None:
    """
    Tries free non-Google vision models on OpenRouter in order.
    Automatically switches to the next model on any error (rate limit, timeout, etc.)
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is not set! Cannot call vision.")
        return None

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        {"type": "text",      "text": prompt},
    ]

    for model in VISION_MODELS:
        try:
            logger.info(f"→ Vision: trying [{model}]…")
            async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization":  f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer":   "https://trading-ai-mentor.onrender.com",
                        "X-Title":        "Trade Mentor Bot",
                        "Content-Type":   "application/json",
                    },
                    json={
                        "model":       model,
                        "messages":    [{"role": "user", "content": content}],
                        "max_tokens":  2048,
                        "temperature": 0.4,
                    },
                )

            data       = resp.json()
            status     = resp.status_code
            error_info = data.get("error", {})

            if status == 429:
                logger.warning(f"✗ [{model}] rate limited (429) — trying next…")
                continue
            if status >= 400:
                logger.warning(f"✗ [{model}] HTTP {status}: {error_info} — trying next…")
                continue

            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text and len(text.strip()) > 15:
                logger.info(f"✅ Vision success via [{model}]")
                return text.strip()
            else:
                logger.warning(f"✗ [{model}] empty/short response: '{text[:80]}' — trying next…")

        except httpx.TimeoutException:
            logger.warning(f"✗ [{model}] timed out — trying next…")
        except Exception as e:
            logger.warning(f"✗ [{model}] exception: {e} — trying next…")

    logger.error("All vision models failed!")
    return None


async def _call_openrouter_text(messages: list[dict]) -> str | None:
    """Tries OpenRouter text-only models with auto-fallback."""
    if not OPENROUTER_API_KEY:
        return None

    for model in TEXT_MODELS_ON_OPENROUTER:
        try:
            logger.info(f"→ OpenRouter text: trying [{model}]…")
            async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer":  "https://trading-ai-mentor.onrender.com",
                        "X-Title":       "Trade Mentor Bot",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "model":       model,
                        "messages":    messages,
                        "max_tokens":  2048,
                        "temperature": 0.4,
                    },
                )

            data   = resp.json()
            status = resp.status_code

            if status == 429:
                logger.warning(f"✗ OpenRouter [{model}] rate limited — trying next…")
                continue
            if status >= 400:
                logger.warning(f"✗ OpenRouter [{model}] HTTP {status} — trying next…")
                continue

            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text and len(text.strip()) > 10:
                logger.info(f"✅ OpenRouter text success via [{model}]")
                return text.strip()

        except Exception as e:
            logger.warning(f"✗ OpenRouter [{model}]: {e}")

    return None


# ─────────────────────────────────────────────────────────────────────────
#  AI Manager — all text + vision tasks
# ─────────────────────────────────────────────────────────────────────────

class AIManagerService:
    def __init__(self):
        self.clients: dict = {}

        _providers = [
            ("groq",       "https://api.groq.com/openai/v1",   GROQ_API_KEY),
            ("sambanova",  "https://api.sambanova.ai/v1",      SAMBANOVA_API_KEY),
            ("hyperbolic", "https://api.hyperbolic.xyz/v1",    HYPERBOLIC_API_KEY),
            ("cerebras",   "https://api.cerebras.ai/v1",       CEREBRAS_API_KEY),
            ("together",   "https://api.together.xyz/v1",      TOGETHER_API_KEY),
            ("mistral",    "https://api.mistral.ai/v1",        MISTRAL_API_KEY),
            ("novita",     "https://api.novita.ai/v3/openai",  NOVITA_API_KEY),
        ]
        for name, base_url, key in _providers:
            if key:
                self.clients[name] = AsyncOpenAI(base_url=base_url, api_key=key)
                logger.info(f"✅ Registered text provider: {name}")

        # Priority: fastest + most generous first
        self.text_priority = ["groq", "sambanova", "hyperbolic", "cerebras",
                               "together", "mistral", "novita"]
        self.text_models = {
            "groq":       "llama-3.3-70b-versatile",
            "sambanova":  "Meta-Llama-3.3-70B-Instruct",
            "hyperbolic": "meta-llama/Llama-3.3-70B-Instruct",
            "cerebras":   "llama-3.3-70b",
            "together":   "meta-llama/Llama-3-70b-chat-hf",
            "mistral":    "mistral-small-latest",
            "novita":     "meta-llama/llama-3.3-70b-instruct",
        }

    async def _text(self, messages: list[dict]) -> str | None:
        """
        Tries all registered text providers in priority order.
        On exhausted quota (429) or error → auto-switches to next provider.
        Final fallback: OpenRouter DeepSeek V3 / Llama 4 Maverick.
        """
        for provider in self.text_priority:
            if provider not in self.clients:
                continue
            try:
                logger.info(f"→ Text: trying [{provider}]…")
                resp = await self.clients[provider].chat.completions.create(
                    model=self.text_models[provider],
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.4,
                )
                text = resp.choices[0].message.content
                if text and len(text.strip()) > 10:
                    logger.info(f"✅ Text success via [{provider}]")
                    return text.strip()
            except Exception as e:
                logger.warning(f"✗ [{provider}]: {e} — switching to next provider…")

        # Last resort — OpenRouter text models
        logger.info("All local providers failed, trying OpenRouter text…")
        return await _call_openrouter_text(messages)

    # ─────────────────────────────────────────────────────────────
    #  1. Read a scanned PDF page via Vision AI
    # ─────────────────────────────────────────────────────────────
    async def read_scanned_page(self, page_image_bytes: bytes, page_num: int) -> str | None:
        if not OPENROUTER_API_KEY:
            return "⚠️ Для чтения сканированных PDF нужен <b>OPENROUTER_API_KEY</b>."

        prompt = (
            f"Это страница {page_num} из учебника по трейдингу (SMC/ICT). "
            "На изображении — отсканированная страница книги.\n\n"
            "Выполни два действия:\n"
            "1. Прочти весь текст на изображении.\n"
            "2. Объясни этот материал ученику ясно и интересно, как харизматичный ментор по трейдингу. "
            "Используй эмодзи (📊 💡 🎯), жирный текст для терминов, списки для структуры.\n\n"
            "Если на странице нет важной теории (оглавление, пустая страница), "
            "скажи: «На этой странице нет важной теории — двигаемся дальше! ➡️»"
        )

        result = await _call_vision(page_image_bytes, prompt)
        if not result:
            return "❌ Не удалось прочитать страницу. Все Vision AI заняты — попробуйте ещё раз."
        return result

    # ─────────────────────────────────────────────────────────────
    #  2. Analyse a trading chart (homework check)
    # ─────────────────────────────────────────────────────────────
    async def analyze_homework(self, image_bytes: bytes, prompt_text: str = "") -> str | None:
        if not OPENROUTER_API_KEY:
            return "⚠️ Для проверки графиков нужен <b>OPENROUTER_API_KEY</b>."

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
            prompt += f"\n\nВопрос ученика к графику: {prompt_text}"

        result = await _call_vision(image_bytes, prompt)
        if not result:
            return "❌ Vision AI сейчас недоступны. Попробуйте ещё раз или опишите сделку текстом."
        return result

    # ─────────────────────────────────────────────────────────────
    #  3. Explain a PDF page (text-only)
    # ─────────────────────────────────────────────────────────────
    async def analyze_theory(self, page_text: str) -> str | None:
        return await self._text([
            {
                "role": "system",
                "content": (
                    "Ты харизматичный ментор по смарт-мани трейдингу (SMC/ICT). "
                    "Объясни материал ученику максимально доступно и интересно. "
                    "Используй эмодзи (📊 💡 🎯 📉), жирный текст для терминов, списки для структуры. "
                    "Общайся как живой наставник, не как робот. "
                    "Если на странице нет важной теории, скажи: «На этой странице нет важной торговой теории — двигаемся дальше! ➡️»"
                ),
            },
            {"role": "user", "content": f"Текст страницы:\n\n{page_text}"},
        ])

    # ─────────────────────────────────────────────────────────────
    #  4. Explain in simpler terms
    # ─────────────────────────────────────────────────────────────
    async def explain_simpler(self, page_text: str) -> str | None:
        return await self._text([
            {
                "role": "system",
                "content": (
                    "Ты терпеливый ментор по трейдингу. Ученик не понял материал. "
                    "Объясни тот же материал максимально ПРОСТЫМ языком, как для абсолютного новичка. "
                    "Используй жизненные аналогии, эмодзи и пункты."
                ),
            },
            {"role": "user", "content": f"Объясни попроще:\n\n{page_text}"},
        ])

    # ─────────────────────────────────────────────────────────────
    #  5. Answer a user's trading question
    # ─────────────────────────────────────────────────────────────
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
