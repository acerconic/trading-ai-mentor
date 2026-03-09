"""
AI service layer.
Vision  → OpenRouter free vision models (NO Google/Gemini)
Text    → Groq, SambaNova, Hyperbolic, OpenRouter DeepSeek/Llama
Auto-fallback: token exhausted → next model automatically.
"""
import re
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
HTTPX_TIMEOUT = 90

# ─────────────────────────────────────────────────────────────────────────
#  TOP-10 FREE VISION MODELS (no Google) — verified on OpenRouter March 2025
#  Bot tries each one automatically when the previous fails/runs out of tokens
# ─────────────────────────────────────────────────────────────────────────
VISION_MODELS = [
    "meta-llama/llama-3.2-11b-vision-instruct:free",  # Llama 3.2 11B Vision ✅
    "nvidia/nemotron-nano-12b-2-vl:free",              # NVIDIA Nemotron VL ✅
    "qwen/qwen3-vl-235b-a22b-thinking",               # Qwen3 VL 235B, $0/$0 ✅
    "meta-llama/llama-3.2-90b-vision-instruct:free",  # Llama 3.2 90B Vision ✅
    "mistralai/mistral-small-3.1-24b-instruct:free",  # Mistral Small 3.1 (vision) ✅
    "moonshotai/moonlight-16b-a3b-instruct:free",     # Moonshot Moonlight ✅
    "bytedance-research/ui-tars-72b:free",            # ByteDance UI-Tars 72B ✅
    "deepseek/deepseek-prover-v2:free",               # DeepSeek Prover V2 ✅
    "qwen/qwen2.5-vl-3b-instruct:free",              # Qwen2.5 VL 3B ✅
    "featherless/qwerky-72b:free",                   # Qwerky 72B fallback
]

# ─────────────────────────────────────────────────────────────────────────
#  TOP-10 FREE TEXT MODELS — generous context, zero cost
# ─────────────────────────────────────────────────────────────────────────
TEXT_MODELS_ON_OPENROUTER = [
    "deepseek/deepseek-chat-v3-0324:free",           # DeepSeek V3 — 64k ctx ✅
    "meta-llama/llama-3.3-70b-instruct:free",        # Llama 3.3 70B ✅
    "qwen/qwen3-235b-a22b:free",                     # Qwen3 235B ✅
    "mistralai/mistral-small-3.1-24b-instruct:free", # Mistral Small 3.1 ✅
    "google/gemma-3-27b-it:free",                    # Gemma 3 27B ✅
    "qwen/qwen3-30b-a3b:free",                       # Qwen3 30B ✅
    "moonshotai/moonlight-16b-a3b-instruct:free",    # Moonshot ✅
    "deepseek/deepseek-r1-zero:free",                # DeepSeek R1 Zero ✅
    "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",  # NVIDIA Nemotron 253B ✅
    "meta-llama/llama-3.1-8b-instruct:free",         # Llama 3.1 8B fast ✅
]


def _md_to_html(text: str) -> str:
    """
    Convert AI markdown output to clean Telegram HTML.
    Removes: **, ###, ---, #tags, raw dashes in lists.
    """
    # Bold: **text** → <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    # Italic: *text* or _text_ → <i>text</i>
    text = re.sub(r'\*([^*\n]+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_([^_\n]+?)_', r'<i>\1</i>', text)
    # Headers: ### Title → <b>Title</b>
    text = re.sub(r'^#{1,6}\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    # Horizontal rules: --- or *** lines → remove
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove raw leftover asterisks and backticks used as bullets
    text = re.sub(r'(?<!\w)\*(?!\w)', '', text)
    # Inline code: `code` → <code>code</code>
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def _call_vision(image_bytes: bytes, prompt: str) -> str | None:
    """
    Auto-iterates through all free vision models.
    On 404/429/error → moves to next automatically.
    Returns first successful non-empty response.
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set.")
        return None

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        {"type": "text", "text": prompt},
    ]

    for model in VISION_MODELS:
        try:
            logger.info(f"→ Vision [{model}]…")
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
            data   = resp.json()
            status = resp.status_code
            if status in (429, 402):
                logger.warning(f"✗ [{model}] tokens exhausted ({status}) → next")
                continue
            if status == 404:
                logger.warning(f"✗ [{model}] not found (404) → next")
                continue
            if status >= 400:
                err = data.get("error", {})
                logger.warning(f"✗ [{model}] HTTP {status}: {err} → next")
                continue
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text and len(text.strip()) > 15:
                logger.info(f"✅ Vision OK [{model}]")
                return _md_to_html(text.strip())
            logger.warning(f"✗ [{model}] empty response → next")
        except httpx.TimeoutException:
            logger.warning(f"✗ [{model}] timeout → next")
        except Exception as e:
            logger.warning(f"✗ [{model}] {e} → next")

    logger.error("All vision models failed!")
    return None


async def _call_openrouter_text(messages: list[dict]) -> str | None:
    """Iterates through free OpenRouter text models with auto-fallback."""
    if not OPENROUTER_API_KEY:
        return None
    for model in TEXT_MODELS_ON_OPENROUTER:
        try:
            logger.info(f"→ OR-text [{model}]…")
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
            if status in (429, 402, 404):
                logger.warning(f"✗ OR-text [{model}] {status} → next")
                continue
            if status >= 400:
                logger.warning(f"✗ OR-text [{model}] HTTP {status} → next")
                continue
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text and len(text.strip()) > 10:
                logger.info(f"✅ OR-text OK [{model}]")
                return _md_to_html(text.strip())
        except Exception as e:
            logger.warning(f"✗ OR-text [{model}] {e} → next")
    return None


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
                logger.info(f"✅ Text provider: {name}")

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
        """Try all registered providers → then OpenRouter 10-model fallback."""
        for provider in self.text_priority:
            if provider not in self.clients:
                continue
            try:
                logger.info(f"→ Text [{provider}]…")
                resp = await self.clients[provider].chat.completions.create(
                    model=self.text_models[provider],
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.4,
                )
                text = resp.choices[0].message.content
                if text and len(text.strip()) > 10:
                    logger.info(f"✅ Text OK [{provider}]")
                    return _md_to_html(text.strip())
            except Exception as e:
                logger.warning(f"✗ [{provider}] {e} → next")
        # Last resort: OpenRouter 10-model pool
        return await _call_openrouter_text(messages)

    # ── System prompt helper ─────────────────────────────────────────────────
    @staticmethod
    def _sys(lang: str) -> str:
        base = (
            "Ты харизматичный ментор по смарт-мани трейдингу (SMC/ICT). "
            if lang != "UZ" else
            "Siz SMC/ICT smart money treydingidan xarizmatik mentorsiz. "
        )
        fmt = (
            "Отвечай в формате Telegram HTML: используй <b>жирный</b> для терминов, "
            "эмодзи (📊💡🎯📉) для структуры. "
            "НИКАКИХ двойных звёздочек (**), решёток (###) или горизонтальных линий (---). "
            "Только чистый текст + HTML-теги."
            if lang != "UZ" else
            "Javobingiz Telegram HTML formatida bo'lsin: <b>qalin</b> — atamalar uchun, "
            "emoji (📊💡🎯📉) — tuzilma uchun. "
            "Ikki yulduzcha (**), (###) yoki (---) ISHLATMANG. Faqat matn + HTML."
        )
        return base + fmt

    # ── read_scanned_page ────────────────────────────────────────────────────
    async def read_scanned_page(self, page_image_bytes: bytes,
                                page_num: int, lang: str = "RU") -> str | None:
        if not OPENROUTER_API_KEY:
            return None
        if lang == "UZ":
            prompt = (
                f"Bu savdo darsligi sahifasi {page_num} (SMC/ICT). "
                "Rasmda skanerlangan kitob sahifasi bor.\n\n"
                "1. Rasmdagi barcha matnni o'qi.\n"
                "2. Materialni o'quvchiga oddiy va qiziqarli tarzda tushuntir — savdo mentori sifatida. "
                "Telegram HTML ishlatamiz: <b>qalin</b> atamalar uchun, emoji 📊💡🎯. "
                "Ikki yulduzcha (**) yoki (###) ISHLATMA.\n\n"
                "Agar sahifada muhim nazariya bo'lmasa: «Bu sahifada muhim nazariya yo'q — davom etamiz! ➡️»"
            )
        else:
            prompt = (
                f"Это страница {page_num} учебника по трейдингу (SMC/ICT). "
                "На изображении — сканированная страница книги.\n\n"
                "1. Прочти текст на изображении.\n"
                "2. Объясни материал ученику живо и интересно.\n"
                "Используй Telegram HTML: <b>жирный</b> для терминов, эмодзи 📊💡🎯. "
                "НЕ используй ** или ###.\n\n"
                "Если нет важной теории — скажи: «На этой странице нет важной теории — двигаемся дальше! ➡️»"
            )
        result = await _call_vision(page_image_bytes, prompt)
        return result or ("❌ Не удалось прочитать страницу. Попробуйте ещё раз."
                          if lang != "UZ" else
                          "❌ Sahifani o'qib bo'lmadi. Qayta urinib ko'ring.")

    # ── analyze_homework ─────────────────────────────────────────────────────
    async def analyze_homework(self, image_bytes: bytes,
                               prompt_text: str = "", lang: str = "RU") -> str | None:
        if not OPENROUTER_API_KEY:
            return ("⚠️ Для проверки графиков нужен <b>OPENROUTER_API_KEY</b>."
                    if lang != "UZ" else
                    "⚠️ Grafiklarni tekshirish uchun <b>OPENROUTER_API_KEY</b> kerak.")
        if lang == "UZ":
            prompt = (
                "Siz SMC/ICT uslubida professional savdo mentori siz. "
                "O'quvchi uy vazifasini tekshirish uchun grafik skrinshot yubordi.\n\n"
                "1. Belgilash to'g'riligini baholang (OB, FVG/IFVG, Likvidlik, BOS/CHoCH, OTE).\n"
                "2. Xatolarni muloyimlik bilan ko'rsating.\n"
                "3. 1-2 ta asosiy maslahat bering.\n"
                "4. Xulosa: ✅ Qabul qilindi / ❌ Qayta ishlang.\n\n"
                "Telegram HTML formatida: <b>qalin</b> atamalar, emoji 📊💡🎯📉. "
                "** va ### ISHLATMA."
            )
        else:
            prompt = (
                "Ты профессиональный ментор по SMC/ICT трейдингу. "
                "Ученик прислал скриншот графика для проверки домашней работы.\n\n"
                "1. Оцени правильность разметки (OB, FVG/IFVG, Ликвидность, BOS/CHoCH, OTE).\n"
                "2. Укажи ошибки тактично.\n"
                "3. Дай 1-2 совета.\n"
                "4. Итог: ✅ Принято / ❌ Доработать.\n\n"
                "Пиши в Telegram HTML: <b>жирный</b> для терминов, эмодзи 📊💡🎯📉. "
                "НЕ используй ** и ###."
            )
        if prompt_text:
            prompt += f"\n\nВопрос ученика: {prompt_text}" if lang != "UZ" else f"\n\nO'quvchi savoli: {prompt_text}"
        result = await _call_vision(image_bytes, prompt)
        return result or ("❌ Vision AI сейчас недоступны. Попробуйте позже."
                          if lang != "UZ" else
                          "❌ Vision AI hozir mavjud emas. Keyinroq urinib ko'ring.")

    # ── analyze_theory ───────────────────────────────────────────────────────
    async def analyze_theory(self, page_text: str, lang: str = "RU") -> str | None:
        sys = self._sys(lang)
        if lang == "UZ":
            user_msg = f"Savdoga oid kitob sahifasi matni:\n\n{page_text}"
        else:
            user_msg = f"Текст страницы книги по трейдингу:\n\n{page_text}"
        return await self._text([
            {"role": "system", "content": sys + (
                "\nЕсли на странице нет важной теории — скажи: «На этой странице нет важной теории — двигаемся дальше! ➡️»"
                if lang != "UZ" else
                "\nAgar sahifada muhim nazariya bo'lmasa: «Bu sahifada muhim nazariya yo'q — davom etamiz! ➡️»"
            )},
            {"role": "user", "content": user_msg},
        ])

    # ── explain_simpler ──────────────────────────────────────────────────────
    async def explain_simpler(self, page_text: str, lang: str = "RU") -> str | None:
        sys = self._sys(lang)
        if lang == "UZ":
            user_msg = f"O'quvchi materialni tushunmadi. Yangi boshlovchi uchun oddiy tilda tushuntir:\n\n{page_text}"
        else:
            user_msg = f"Ученик не понял материал. Объясни максимально простым языком для новичка:\n\n{page_text}"
        return await self._text([{"role": "system", "content": sys},
                                  {"role": "user", "content": user_msg}])

    # ── answer_question ──────────────────────────────────────────────────────
    async def answer_question(self, question: str, lang: str = "RU") -> str | None:
        sys = (
            "Ты эксперт по SMC/ICT трейдингу. Дай чёткий HTML-ответ. "
            "Эмодзи, <b>жирный</b> для терминов. НЕ используй ** и ###."
            if lang != "UZ" else
            "Siz SMC/ICT savdo mutaxassisiz. Aniq HTML javob bering. "
            "Emoji, <b>qalin</b> atamalar uchun. ** va ### ISHLATMANG."
        )
        return await self._text([{"role": "system", "content": sys},
                                  {"role": "user", "content": question}])


# Singleton
gemini_service = AIManagerService()
