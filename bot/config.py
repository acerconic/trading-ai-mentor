import os
from dotenv import load_dotenv

# Load environment variables from .env file or rely on system vars
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8780676656:AAECnqJOHWYAYXXGjhIIGTy5rBPx5QMkjK0")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "217924651"))
except ValueError:
    ADMIN_ID = 217924651

# Provider API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
TRANSCRIPT_API_KEY = os.getenv("CLOUDFLARE_API_KEY", "") # for potential future usage
