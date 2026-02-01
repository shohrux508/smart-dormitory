import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from app.database import SessionLocal, TelegramUser
from sqlalchemy.future import select

# Load environment variables
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEB_URL")

if WEBAPP_URL and not WEBAPP_URL.startswith("http"):
    WEBAPP_URL = f"https://{WEBAPP_URL}"

# Configure logging
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = None
dp = None

if TELEGRAM_TOKEN:
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()
else:
    print(f"DEBUG: Looking for .env at: {env_path}")
    print(f"DEBUG: BOT_TOKEN env var is: {os.getenv('BOT_TOKEN')}")
    logger.warning("BOT_TOKEN not found in environment variables. Bot will not start.")

async def cmd_start(message: types.Message):
    """/start command handler."""
    # Register user
    user = message.from_user
    db = SessionLocal()
    try:
        db_user = db.query(TelegramUser).filter(TelegramUser.chat_id == user.id).first()
        if not db_user:
            db_user = TelegramUser(
                chat_id=user.id,
                first_name=user.first_name,
                username=user.username
            )
            db.add(db_user)
            db.commit()
            logger.info(f"New Telegram user registered: {user.id}")
    except Exception as e:
        logger.error(f"Error registering user: {e}")
    finally:
        db.close()

    if not WEBAPP_URL:
        await message.answer("WebApp URL not configured.")
        return

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Open Dashboard", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    
    await message.answer("Welcome to Smart Dormitory Bot! Click below to open the dashboard.", reply_markup=markup)

# Register handlers
if dp:
    dp.message.register(cmd_start, Command("start"))

async def start_bot():
    """Starts the Telegram bot polling."""
    if not bot or not dp:
        logger.warning("Bot is not initialized. Skipping start.")
        return

    logger.info("Starting Telegram Bot polling...")
    try:
        # Provide the bot instance to the dispatcher
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in bot polling: {e}")

async def stop_bot():
    """Stops the bot session."""
    if bot:
        logger.info("Stopping Telegram Bot...")
        await bot.session.close()

async def notify_all_users(message: str):
    """Sends a notification to all registered users."""
    if not bot:
        return
        
    db = SessionLocal()
    try:
        users = db.query(TelegramUser).all()
        for user in users:
            try:
                await bot.send_message(chat_id=user.chat_id, text=message)
            except Exception as e:
                logger.error(f"Failed to send notification to {user.chat_id}: {e}")
    except Exception as e:
        logger.error(f"Error fetching users for notification: {e}")
    finally:
        db.close()
