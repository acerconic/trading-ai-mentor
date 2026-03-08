import os
from dotenv import load_dotenv

# Load environment variables from .env file or rely on system vars
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8780676656:AAECnqJOHWYAYXXGjhIIGTy5rBPx5QMkjK0")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "217924651"))
except ValueError:
    ADMIN_ID = 217924651

# Read GEMINI_API_KEYS (comma separated) and convert to a list
gemini_keys_env = os.getenv(
    "GEMINI_API_KEYS", 
    "AIzaSyAsiAnmieeFo5csQnyMNjmD8XgQ814mEws,AIzaSyDEdCyHtYEfoU81A1Gck9Bqa8jKStcmmzI,AIzaSyDharJ7xfkoxHLlad0MHRhhoEUPeAX4vrI"
)
GEMINI_API_KEYS = [key.strip() for key in gemini_keys_env.split(",") if key.strip()]
