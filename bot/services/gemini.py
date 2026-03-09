import logging
import asyncio
from openai import AsyncOpenAI
from google import genai
from google.genai import types as genai_types
from config import GROQ_API_KEY, CEREBRAS_API_KEY, TOGETHER_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)


class AIManagerService:
    def __init__(self):
        # Configure Async OpenAI-compatible clients for text providers
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

        # Priority list for text analysis tasks
        self.text_priority = ['cerebras', 'groq', 'together']
        # Route mapping for text models (all top-tier Llama 3 70B+)
        self.text_models = {
            'cerebras': 'llama-3.3-70b',
            'groq': 'llama-3.3-70b-versatile',
            'together': 'meta-llama/Llama-3-70b-chat-hf'
        }

        # Gemini Vision client (new SDK)
        self._gemini_client = None
        if GEMINI_API_KEY:
            try:
                self._gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("✅ Gemini Vision client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to init Gemini client: {e}")

    async def _generate_text_fallback(self, prompt: str) -> str | None:
        """Tries text generation across multiple fast providers until success."""
        if not self.clients:
            logger.error("No API keys configured!")
            return None

        for provider in self.text_priority:
            if provider not in self.clients:
                continue

            client = self.clients[provider]
            model_name = self.text_models[provider]

            try:
                logger.info(f"Attempting text generation via {provider} ({model_name})...")
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2048,
                    temperature=0.3
                )
                logger.info(f"Success via {provider}!")
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Failed via {provider}: {e}. Trying next provider...")
                continue

        logger.error("All text providers failed.")
        return None

    async def analyze_homework(self, image_bytes: bytes, prompt_text: str = "") -> str | None:
        """Vision analysis using Google Gemini 2.0 Flash for parsing chart screenshots."""
        if not self._gemini_client:
            return (
                "⚠️ Для проверки графиков необходим <b>GEMINI_API_KEY</b>.\n\n"
                "Получите его бесплатно на <a href='https://aistudio.google.com/'>aistudio.google.com</a> "
                "и добавьте в переменные окружения на Render."
            )

        try:
            vision_prompt = (
                "Ты профессиональный ментор по трейдингу в стиле SMC/ICT. "
                "Ученик прислал скриншот своего графика для проверки домашнего задания. "
                "Внимательно проанализируй разметку на графике.\n\n"
            )
            if prompt_text:
                vision_prompt += f"Вопрос ученика: {prompt_text}\n\n"

            vision_prompt += (
                "Выполни следующее:\n"
                "1. Оцени правильность разметки (Orderblocks, FVG/IFVG, Liquidity,  BOS/CHoCH, OTE).\n"
                "2. Укажи на ошибки конкретно и тактично.\n"
                "3. Дай 1-2 ключевых совета по улучшению.\n"
                "4. В конце поставь оценку: ✅ Принято / ❌ Доработать.\n\n"
                "Формат: структурированный, с эмодзи (📊 💡 🎯 📉), профессиональный тон наставника."
            )

            # Use asyncio.to_thread to avoid blocking the event loop
            response = await asyncio.to_thread(
                self._gemini_client.models.generate_content,
                model="gemini-2.0-flash",
                contents=[
                    genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    vision_prompt
                ]
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini Vision analysis failed: {e}")
            return "❌ При анализе графика произошла ошибка. Убедитесь, что картинка чёткая и попробуйте снова."

    async def analyze_theory(self, text_chunk: str, image_bytes: bytes = None) -> str | None:
        """Processes and simplifies trading theory for a student via Text Analysis."""
        prompt = (
            "Действуй как высококлассный, харизматичный ментор по смарт-мани трейдингу (SMC/ICT). "
            "Твоя задача — проанализировать текст со страницы книги по трейдингу и объяснить его ученику максимально доступно, "
            "интересно и профессионально.\n\n"
            "ТРЕБОВАНИЯ К ОТВЕТУ:\n"
            "1. Не говори как робот или ИИ, общайся как живой наставник (например: «Давайте разберем...» или «Суть здесь в том, что...»).\n"
            "2. Обязательно используй релевантные эмодзи (📊, 💡, 🎯, 📉 и тд) для визуального оформления.\n"
            "3. Используй жирный шрифт для ключевых терминов и списки для структуры. Красота оформления крайне важна!\n"
            "4. Объясняй сложные концепции простыми словами или аналогиями из жизни.\n"
            "5. Если на странице только вода, оглавление или нет важной теории — просто скажи: «На этой странице нет важной торговой теории, мы можем смело двигаться дальше! ➡️».\n\n"
            f"РАЗБЕРИ ЭТОТ МАТЕРИАЛ:\n{text_chunk}"
        )
        return await self._generate_text_fallback(prompt)


# Ready-to-use routing Service Singleton
gemini_service = AIManagerService()  # Variable name kept for backward compatibility
