import aiosqlite
import logging

DB_NAME = "trading_mentor.sqlite"

class Database:
    @staticmethod
    async def init_db():
        """Creates the 'users' table if it doesn't exist."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        telegram_id INTEGER PRIMARY KEY,
                        username TEXT,
                        language TEXT DEFAULT NULL,
                        is_approved BOOLEAN DEFAULT FALSE,
                        studied_books INTEGER DEFAULT 0,
                        hw_attempts INTEGER DEFAULT 0,
                        hw_fails INTEGER DEFAULT 0
                    )
                ''')
                await db.commit()
            logging.info("Database initialized successfully.")
        except Exception as e:
            logging.error(f"Error initializing DB: {e}")

    @staticmethod
    async def add_user(telegram_id: int, username: str) -> None:
        """Adds a new user if not exists."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
                    (telegram_id, username)
                )
                await db.commit()
        except Exception as e:
            logging.error(f"Error adding user {telegram_id}: {e}")

    @staticmethod
    async def get_user(telegram_id: int) -> dict | None:
        """Retrieves user by telegram_id."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logging.error(f"Error getting user {telegram_id}: {e}")
            return None

    @staticmethod
    async def update_approval(telegram_id: int, is_approved: bool) -> None:
        """Updates user approval status."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    "UPDATE users SET is_approved = ? WHERE telegram_id = ?",
                    (is_approved, telegram_id)
                )
                await db.commit()
        except Exception as e:
            logging.error(f"Error updating approval for {telegram_id}: {e}")

    @staticmethod
    async def update_language(telegram_id: int, language: str) -> None:
        """Updates user language (RU/UZ)."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    "UPDATE users SET language = ? WHERE telegram_id = ?",
                    (language, telegram_id)
                )
                await db.commit()
        except Exception as e:
            logging.error(f"Error updating language for {telegram_id}: {e}")

    @staticmethod
    async def increment_studied_books(telegram_id: int) -> None:
        """Increments internal count of studied books for user."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    "UPDATE users SET studied_books = studied_books + 1 WHERE telegram_id = ?",
                    (telegram_id,)
                )
                await db.commit()
        except Exception as e:
            logging.error(f"Error incrementing studied_books for {telegram_id}: {e}")

    @staticmethod
    async def record_hw_attempt(telegram_id: int, failed: bool = False) -> None:
        """Records homework attempt and optionally failure."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                if failed:
                    await db.execute(
                        "UPDATE users SET hw_attempts = hw_attempts + 1, hw_fails = hw_fails + 1 WHERE telegram_id = ?",
                        (telegram_id,)
                    )
                else:
                    await db.execute(
                        "UPDATE users SET hw_attempts = hw_attempts + 1 WHERE telegram_id = ?",
                        (telegram_id,)
                    )
                await db.commit()
        except Exception as e:
            logging.error(f"Error recording homework attempt for {telegram_id}: {e}")

    @staticmethod
    async def get_stats(telegram_id: int) -> dict:
        """Quickly retrieves user stats logic."""
        user = await Database.get_user(telegram_id)
        if not user:
            return {}
        
        attempts = user["hw_attempts"]
        fails = user["hw_fails"]
        winrate = 0.0
        if attempts > 0:
            success = attempts - fails
            winrate = (success / attempts) * 100
            
        return {
            "studied_books": user["studied_books"],
            "hw_attempts": attempts,
            "hw_fails": fails,
            "winrate": round(winrate, 2)
        }
