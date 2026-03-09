import logging
import asyncio
from openai import AsyncOpenAI
from config import GROQ_API_KEY, CEREBRAS_API_KEY, TOGETHER_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)

# ─────────────────────── Lazy Gemini Vision setup ───────────────────────
_gemini_client = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("✅ Gemini Vision client initialized.")
        except Exception as e:
            logger.error(f"Gemini client init failed: {e}")
    return _gemini_client


class AIManagerService:
    def __init__(self):
        self.clients = {}

        if GROQ_API_KEY:
            self.clients['groq'] = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=GROQ_API_KEY
            )
        if CEREBRAS_API_KEY:
            self.clients['cerebras'] = AsyncOpenAI(
                base_url="https://api.cerebras.ai/v1",
                api_key=CEREBRAS_API_KEY
            )
        if TOGETHER_API_KEY:
            self.clients['together'] = AsyncOpenAI(
                base_url="https://api.together.xyz/v1",
                api_key=TOGETHER_API_KEY
            )

        self.text_priority = ['cerebras', 'groq', 'together']
        self.text_models = {
            'cerebras': 'llama-3.3-70b',
            'groq':     'llama-3.3-70b-versatile',
            'together': 'meta-llama/Llama-3-70b-chat-hf',
        }

    async def _generate_text_fallback(self, messages: list[dict]) -> str | None:
        """Sends a ready-made messages list to available providers, trying each one."""
        if not self.clients:
            logger.error("No text API keys configured.")
            return None

        for provider in self.text_priority:
            if provider not in self.clients:
                continue
            client    = self.clients[provider]
            model_name = self.text_models[provider]
            try:
                logger.info(f"→ Trying {provider} ({model_name})…")
                resp = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.4,
                )
                logger.info(f"✅ Success via {provider}")
                return resp.choices[0].message.content
            except Exception as e:
                logger.warning(f"✗ {provider} failed: {e}")
                continue

        logger.error("All text providers failed.")
        return None

    # ──────────────────────────────────────────────
    #  Vision: analyse a trading chart image
    # ──────────────────────────────────────────────
    async def analyze_homework(self, image_bytes: bytes, prompt_text: str = "") -> str | None:
        client = _get_gemini()
        if not client:
            return (
                "⚠️ Для проверки графиков нужен <b>GEMINI_API_KEY</b>.\n\n"
                "Получите его бесплатно на <a href='https://aistudio.google.com/'>aistudio.google.com</a> "
                "и добавьте в переменные окружения Render."
            )
        try:
            from google.genai import types as gt

            system_instruction = (
                "Ты профессиональный ментор по трейдингу в стиле SMC/ICT. "
                "Ученик прислал скриншот своего графика для проверки домашнего задания. "
                "Проанализируй разметку внимательно.\n\n"
                "Что нужно сделать:\n"
                "1. Оцени правильность разметки (Orderblocks, FVG/IFVG, Liquidity, BOS/CHoCH, OTE).\n"
                "2. Укажи на конкретные ошибки тактично.\n"
                "3. Дай 1-2 ключевых совета по улучшению.\n"
                "4. Заверши оценкой: ✅ Принято / ❌ Доработать.\n\n"
                "Формат: структурированный, с эмодзи (📊 💡 🎯 📉), тон наставника, без лишней воды."
            )
            if prompt_text:
                system_instruction += f"\n\nДополнительный вопрос от ученика: {prompt_text}"

            # Correct call format for google-genai >= 1.0
            def _call():
                img_part = gt.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                txt_part = gt.Part.from_text(text=system_instruction)
                content  = gt.Content(parts=[img_part, txt_part])
                return client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[content],
                )

            response = await asyncio.to_thread(_call)
            return response.text

        except Exception as e:
            logger.error(f"Gemini Vision failed: {e}", exc_info=True)
            return "❌ При анализе графика произошла ошибка. Попробуйте снова или пришлите более чёткое изображение."

    # ──────────────────────────────────────────────
    #  Theory: explain a page of a PDF
    # ──────────────────────────────────────────────
    async def analyze_theory(self, page_text: str) -> str | None:
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты харизматичный ментор по смарт-мани трейдингу (SMC/ICT). "
                    "Объясни материал ученику максимально доступно и интересно. "
                    "Используй эмодзи (📊 💡 🎯 📉), жирный текст для терминов и списки для структуры. "
                    "Общайся как живой наставник, а не как робот. "
                    "Если на странице нет важной теории, скажи: «На этой странице нет важной торговой теории — двигаемся дальше! ➡️»"
                ),
            },
            {
                "role": "user",
                "content": f"Вот текст страницы книги по трейдингу:\n\n{page_text}",
            },
        ]
        return await self._generate_text_fallback(messages)

    # ──────────────────────────────────────────────
    #  Re-explain with simpler language
    # ──────────────────────────────────────────────
    async def explain_simpler(self, page_text: str) -> str | None:
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты терпеливый ментор по трейдингу. Ученик не понял материал с первого раза. "
                    "Объясни тот же материал максимально ПРОСТЫМ языком, как для абсолютного новичка. "
                    "Используй реальные жизненные аналогии, подчёркивай самое главное, избегай сложных слов. "
                    "Используй эмодзи и структуру."
                ),
            },
            {
                "role": "user",
                "content": f"Объясни попроще:\n\n{page_text}",
            },
        ]
        return await self._generate_text_fallback(messages)

    # ──────────────────────────────────────────────
    #  Answer a specific user question about trading
    # ──────────────────────────────────────────────
    async def answer_question(self, question: str) -> str | None:
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты эксперт по смарт-мани трейдингу (SMC/ICT). "
                    "Дай чёткий, грамотный, структурированный ответ на вопрос ученика. "
                    "Используй эмодзи, жирный текст и примеры. Отвечай кратко и по делу."
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ]
        return await self._generate_text_fallback(messages)


# Singleton
gemini_service = AIManagerService()
