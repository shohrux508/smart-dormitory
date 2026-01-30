import aiosqlite
import asyncio

DB_NAME = "room.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                user_task TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()

async def get_setting(key: str, default: str = None):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def add_user(telegram_id: int, username: str | None, full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            # Use UPSERT to update username/fullname if user already exists
            # This ensures we always have the latest username for /settask
            await db.execute("""
                INSERT INTO users (telegram_id, username, full_name) 
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name
            """, (telegram_id, username, full_name))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def remove_user(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        await db.commit()

async def get_users():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT telegram_id, username, full_name, user_task, joined_at FROM users") as cursor:
            # Convert to list of dicts for easier handling
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_user_by_username(username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        # Case insensitive search usually desirable, but explicit match is safer for now unless we use NOCASE collation
        async with db.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def update_user_task(telegram_id: int, task_text: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET user_task = ? WHERE telegram_id = ?", (task_text, telegram_id))
        await db.commit()

async def get_user_count():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

if __name__ == "__main__":
    # Self-check logic
    asyncio.run(init_db())
    print("Database initialized.")
