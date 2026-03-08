import logging
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError

from config import GEMINI_API_KEYS

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_keys = GEMINI_API_KEYS
        self.current_key_idx = 0
        self.model = None
        self._configure_client()

    def _configure_client(self):
        """Initializes client with the current active key."""
        if not self.api_keys:
            logger.error("No Gemini API keys provided in configuration.")
            return
        
        current_key = self.api_keys[self.current_key_idx]
        genai.configure(api_key=current_key)
        # We recommend gemini-1.5-flash for the perfect balance of speed and multi-modal readiness
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info(f"Configured Gemini API with key index {self.current_key_idx}.")

    def _rotate_key(self):
        """Rotates the API key upon encountering rate limits."""
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        logger.warning(f"Rotating Gemini API Key. Switched to index {self.current_key_idx}.")
        self._configure_client()

    async def _generate_content_with_retry(self, contents: list, retries: int = None) -> str | None:
        """Helper to call Gemini API with key rotation on ResourceExhausted (429)."""
        if retries is None:
            # Try enough times to loop through all available keys
            retries = len(self.api_keys) + 1 

        for attempt in range(retries):
            try:
                response = await self.model.generate_content_async(contents)
                return response.text
            except ResourceExhausted as e:
                logger.warning(f"ResourceExhausted (429) on key index {self.current_key_idx}. Attempt {attempt + 1}/{retries}.")
                self._rotate_key()
            except GoogleAPIError as e:
                logger.error(f"GoogleAPIError during generation: {e}")
                if attempt == retries - 1:
                    return None
            except Exception as e:
                logger.error(f"Unexpected error in Gemini API call: {e}")
                return None
                
        logger.error("All Gemini API retries exhausted.")
        return None

    async def analyze_homework(self, image_bytes: bytes, prompt_text: str = "") -> str | None:
        """Analyzes a student's trading chart homework."""
        sys_prompt = (
            "Ты профессиональный трейдер институционального уровня и строгий ментор. "
            "Проверь график. Твой ответ ВСЕГДА из 3 блоков: "
            "1. Краткая суть. "
            "2. Детальный разбор (SMC, ICT). "
            "3. Вердикт (сдал/не сдал)."
        )
        
        full_text = f"{sys_prompt}\n\nДополнительный комментарий: {prompt_text}" if prompt_text else sys_prompt
        
        image_part = {
            "mime_type": "image/jpeg", # Defaulting to jpeg, works perfectly for typical TG image bytes
            "data": image_bytes
        }
        
        contents = [full_text, image_part]
        return await self._generate_content_with_retry(contents)

    async def analyze_theory(self, text_chunk: str, image_bytes: bytes = None) -> str | None:
        """Processes and simplifies trading theory for a student."""
        prompt = (
            "Действуй как профессиональный ментор по трейдингу. "
            "Объясни и структурируй следующий материал простым и понятным языком. "
            "Выдели главные мысли.\n\n"
            f"Материал:\n{text_chunk}"
        )
        
        contents = [prompt]
        if image_bytes:
            contents.append({
                "mime_type": "image/jpeg",
                "data": image_bytes
            })
            
        return await self._generate_content_with_retry(contents)

# Ready-to-use Service Singleton
gemini_service = GeminiService()
