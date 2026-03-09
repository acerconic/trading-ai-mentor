import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8780676656:AAECnqJOHWYAYXXGjhIIGTy5rBPx5QMkjK0")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "217924651"))
except ValueError:
    ADMIN_ID = 217924651

# ── Text AI providers (priority: fastest first) ─────────────────────────
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
CEREBRAS_API_KEY  = os.getenv("CEREBRAS_API_KEY", "")
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "")
HYPERBOLIC_API_KEY = os.getenv("HYPERBOLIC_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")   # also used for Vision
TOGETHER_API_KEY  = os.getenv("TOGETHER_API_KEY", "")
MISTRAL_API_KEY   = os.getenv("MISTRAL_API_KEY", "")
NOVITA_API_KEY    = os.getenv("NOVITA_API_KEY", "")
