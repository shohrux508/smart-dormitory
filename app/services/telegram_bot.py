import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from app.database import SessionLocal, TelegramUser, TelegramBookmark
from sqlalchemy.future import select

# Load environment variables
from app.config import settings

TELEGRAM_TOKEN = settings.BOT_TOKEN
WEBAPP_URL = settings.WEB_URL

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

    # Append user_id to URL for personalized dashboard
    sep = "&" if "?" in WEBAPP_URL else "?"
    user_url = f"{WEBAPP_URL}{sep}user_id={user.id}"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Open My Dashboard", web_app=WebAppInfo(url=user_url))]
    ])
    
    await message.answer(
        f"👋 Welcome to Smart Dormitory!\n\n"
        f"Your ID: `{user.id}`\n\n"
        f"To add a device, send:\n`/add <device_id> [name]`\n"
        f"Example: `/add desk_lamp My Lamp`\n\n"
        f"Click below to control your devices:", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

async def cmd_add_device(message: types.Message):
    """/add <device_id> [name]"""
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Usage: `/add <device_id> [optional_name]`", parse_mode="Markdown")
        return
    
    device_id = args[1]
    custom_name = args[2] if len(args) > 2 else device_id
    user_id = message.from_user.id
    
    db = SessionLocal()
    try:
        # Check if already exists
        exists = db.query(TelegramBookmark).filter(
            TelegramBookmark.telegram_id == user_id,
            TelegramBookmark.device_id == device_id
        ).first()
        
        if exists:
            await message.answer(f"⚠️ Device `{device_id}` is already in your list!", parse_mode="Markdown")
            return
            
        bookmark = TelegramBookmark(
            telegram_id=user_id,
            device_id=device_id,
            custom_name=custom_name,
            room="Default"
        )
        db.add(bookmark)
        db.commit()
        await message.answer(f"✅ Device `{device_id}` added successfully!\nOpen the dashboard to see it.", parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error adding device: {e}")
        await message.answer("❌ Failed to add device. Please try again.")
    finally:
        db.close()

# Register handlers
if dp:
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_add_device, Command("add"))

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
