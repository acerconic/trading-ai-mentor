import logging
from openai import AsyncOpenAI
from config import GROQ_API_KEY, CEREBRAS_API_KEY, TOGETHER_API_KEY

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
        """Vision is currently disabled. Return a polite maintenance message."""
        return "⚠️ Проверка графиков временно недоступна, так как текущие ИИ-серверы не поддерживают оптическое зрение (Vision). Попробуйте описать свою сделку текстом."

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

