import logging
import asyncio
from openai import AsyncOpenAI
import google.generativeai as genai
from config import GROQ_API_KEY, CEREBRAS_API_KEY, TOGETHER_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)

class AIManagerService:
    def __init__(self):
        # Configure Async Clients for each active provider
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
        """Vision analysis using Google Gemini Pro Vision (free tier) for parsing charts."""
        if not GEMINI_API_KEY:
            return "⚠️ Для проверки графиков по картинкам (Vision) требуется `GEMINI_API_KEY`. Пожалуйста, добавьте его в админ-панели платформы или в файл .env. Пока что вы можете описывать свои сделки текстом."
            
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model_vision = genai.GenerativeModel('gemini-1.5-flash')
            
            # Prepare image part for Gemini format
            image_parts = [{"mime_type": "image/jpeg", "data": image_bytes}]
            
            vision_prompt = (
                "Ты профессиональный ментор по трейдингу (SMC/ICT). Ученик прислал тебе "
                "скриншот своего графика для проверки. Внимательно проанализируй график. "
                "Если ученик задал вопрос к этому графику, ответ на него: " + prompt_text + "\n\n"
                "Если вопроса нет, просто укажи на правильность отметок (Orderblocks, FVG, Liquidity), "
                "дай конструктивную критику и укажи на ошибки. "
                "Пиши тактично, харизматично, используй структуру (маркированные списки) и эмодзи (📊, 💡, 🎯)."
            )
            
            # Using asyncio to prevent blocking the async loop with the sync call
            response = await asyncio.to_thread(model_vision.generate_content, [vision_prompt, image_parts[0]])
            return response.text
        except Exception as e:
            logger.error(f"Failed to analyze logic via Gemini: {e}")
            return "❌ При анализе графика произошла ошибка. Пожалуйста, убедитесь, что картинка четкая."

    async def analyze_theory(self, text_chunk: str, image_bytes: bytes = None) -> str | None:
        """Processes and simplifies trading theory for a student purely via Text Analysis."""
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
gemini_service = AIManagerService() # Kept variable name 'gemini_service' to avoid editing ALL routers

