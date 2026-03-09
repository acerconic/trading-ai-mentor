import logging
import base64
import json
from openai import AsyncOpenAI
from config import GROQ_API_KEY, OPENROUTER_API_KEY, CEREBRAS_API_KEY, TOGETHER_API_KEY

logger = logging.getLogger(__name__)

class AIManagerService:
    def __init__(self):
        # Configure Async Clients for each provider
        self.clients = {}
        
        if OPENROUTER_API_KEY:
            self.clients['openrouter'] = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
            )
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

        # Priority list for text-only tasks
        self.text_priority = ['cerebras', 'groq', 'openrouter', 'together']
        # Route mapping for text tasks
        self.text_models = {
            'cerebras': 'llama-3.3-70b',
            'groq': 'llama-3.3-70b-versatile',
            'openrouter': 'qwen/qwen3-coder:free',
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

    async def _generate_vision(self, prompt: str, image_bytes: bytes) -> str | None:
        """Vision tasks strictly require OpenRouter currently."""
        if 'openrouter' not in self.clients:
            logger.error("Vision task requested but OpenRouter key is not set.")
            return None
            
        client = self.clients['openrouter']
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        try:
            logger.info("Attempting vision generation via OpenRouter (google/gemini-2.5-flash-free)...")
            response = await client.chat.completions.create(
                model="google/gemini-2.5-flash-free", # Free robust vision model on OpenRouter
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2048,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenRouter Vision API failed: {e}")
            return None

    async def analyze_homework(self, image_bytes: bytes, prompt_text: str = "") -> str | None:
        """Analyzes a student's trading chart homework using Vision."""
        sys_prompt = (
            "Ты профессиональный трейдер институционального уровня и строгий ментор. "
            "Проверь график. Твой ответ ВСЕГДА из 3 блоков:\n"
            "1. Краткая суть.\n"
            "2. Детальный разбор (SMC, ICT).\n"
            "3. Вердикт (сдал/не сдал)."
        )
        
        full_text = f"{sys_prompt}\n\nДополнительный комментарий: {prompt_text}" if prompt_text else sys_prompt
        return await self._generate_vision(full_text, image_bytes)

    async def analyze_theory(self, text_chunk: str, image_bytes: bytes = None) -> str | None:
        """Processes and simplifies trading theory for a student."""
        prompt = (
            "Действуй как профессиональный ментор по трейдингу. "
            "Объясни и структурируй следующий материал простым и понятным языком. "
            "Выдели главные мысли.\n\n"
            f"Материал:\n{text_chunk}"
        )
        
        if image_bytes:
            return await self._generate_vision(prompt, image_bytes)
        else:
            return await self._generate_text_fallback(prompt)

# Ready-to-use routing Service Singleton
gemini_service = AIManagerService() # Kept variable name 'gemini_service' to avoid editing ALL routers

