import asyncio
import logging
import os
import sys
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, filters
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import database
import scheduler

# Load environment variables
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = None
if os.getenv("ADMIN_ID"):
    try:
        ADMIN_ID = int(os.getenv("ADMIN_ID"))
    except ValueError:
        logging.error("⛔ ADMIN_ID in .env is not an integer.")

# Initialize Dispatcher
dp = Dispatcher()

async def on_startup(bot: Bot):
    """Callback triggered when the bot starts polling."""
    await database.init_db()
    logging.info("Database initialized successfully.")
    await scheduler.start_scheduler(bot)

async def main():
    # Basic logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )

    if not TOKEN:
        logging.error("⛔ Error: BOT_TOKEN is missing! Please check your .env file.")
        sys.exit(1)

    # Initialize Bot
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Register start-up hook
    dp.startup.register(on_startup)
    
    # --- Handlers ---

    @dp.message(filters.Command("start"))
    async def cmd_start(message: types.Message):
        """Handle /start command: register user."""
        user = message.from_user
        if not user:
            return
        # Register or User Update
        # We try to add immediately. 
        # But we must respect the limit if it's a NEW user.
        
        existing_user = await database.get_user(user.id)
        
        if not existing_user:
            # Check capacity only for new users
            count = await database.get_user_count()
            if count >= 4:
                await message.reply("⛔ Комната заполнена (4/4).")
                return

        # Register / Update info
        full_name = user.full_name
        success = await database.add_user(user.id, user.username, full_name)
        
        if success:
            if existing_user:
                 await message.reply(f"🔄 Данные обновлены, {full_name}!")
            else:
                 await message.reply(f"✅ Добро пожаловать, {full_name}!")
        else:
            await message.reply("❌ Ошибка при регистрации.")





    @dp.message(filters.Command("leave"))
    async def cmd_leave(message: types.Message):
        """Handle /leave command: remove user."""
        user = message.from_user
        if not user:
            return

        existing_user = await database.get_user(user.id)
        if existing_user:
            await database.remove_user(user.id)
            await message.reply("👋 Вы покинули комнату.", reply_markup=types.ReplyKeyboardRemove())
        else:
            await message.reply("🤔 Вы и так не в комнате.")

    @dp.message(filters.Command("status"))
    async def cmd_status(message: types.Message):
        """Handle /status command: show participants."""
        users = await database.get_users()
        count = len(users)
        
        text = [f"📊 **Статус комнаты** ({count}/4):"]
        
        if not users:
            text.append("<i>Пока никого нет.</i>")
        else:
            for idx, u in enumerate(users, start=1):
                task = u['user_task'] if u['user_task'] else "<i>(нет задачи)</i>"
                if u['username']:
                    user_ref = f"(@{u['username']})"
                else:
                    # Provide ID for admin reference if username is missing
                    user_ref = f"[ID: <code>{u['telegram_id']}</code>]"
                
                text.append(f"{idx}. {u['full_name']} {user_ref} — {task}")
        
        await message.reply("\n".join(text))

    @dp.message(filters.Command("settask"))
    async def cmd_settask(message: types.Message):
        """Handle /settask. Supports reply or @username/ID arguments."""
        user = message.from_user
        if not user or user.id != ADMIN_ID:
            return 

        # 1. Mode: Reply to user
        if message.reply_to_message and message.reply_to_message.from_user:
            target_telegram_id = message.reply_to_message.from_user.id
            
            # Parse task text (everything after command)
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                 await message.reply("⚠️ Введите текст задачи после команды.")
                 return
            task_text = parts[1]
            
            # Check if user exists in DB
            db_user = await database.get_user(target_telegram_id)
            if not db_user:
                # Optional: Auto-register him? No, spec says specs limitations.
                await message.reply("❌ Этот пользователь не зарегистрирован в боте.")
                return

            await database.update_user_task(target_telegram_id, task_text)
            await message.reply(f"✅ Для {db_user['full_name']} установлена задача:\n📝 {task_text}")
            return

        # 2. Mode: Explicit arguments /settask @username Task OR /settask ADS_ID Task
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            await message.reply(
                "⚠️ Используйте **Reply** на сообщение пользователя\n"
                "Или формат: <code>/settask @username Текст</code>\n"
                "Или: <code>/settask ID Текст</code>"
            )
            return
        
        target_identifier = args[1]
        task_text = args[2]
        
        target_user = None

        # Try by Username
        if target_identifier.startswith("@"):
            clean_username = target_identifier[1:]
            target_user = await database.get_user_by_username(clean_username)
        # Try by ID (if digit)
        elif target_identifier.isdigit():
            target_user = await database.get_user(int(target_identifier))
        # Try by raw username (without @)
        else:
            target_user = await database.get_user_by_username(target_identifier)

        if not target_user:
            await message.reply(f"❌ Пользователь \"{target_identifier}\" не найден в базе.\nПопросите его нажать /start для обновления данных.")
            return

        await database.update_user_task(target_user['telegram_id'], task_text)
        await message.reply(f"✅ Для {target_user['full_name']} установлена задача:\n📝 {task_text}")

    @dp.message(filters.Command("set_time"))
    async def cmd_set_time(message: types.Message):
        """Handle /set_time HH:MM"""
        user = message.from_user
        if not user or user.id != ADMIN_ID:
            return 

        args = message.text.split()
        if len(args) < 2:
            await message.reply("⚠️ Формат: <code>/set_time HH:MM</code>")
            return
        
        time_str = args[1]
        try:
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError
        except ValueError:
            await message.reply("⚠️ Неверный формат времени. Используйте HH:MM (00:00 - 23:59).")
            return

        # Save to DB
        await database.set_setting("daily_time", f"{hour:02d}:{minute:02d}")
        
        # Reschedule
        success = await scheduler.reschedule_daily_message(hour, minute, bot)
        
        if success:
            await message.reply(f"✅ Время уведомлений изменено на {hour:02d}:{minute:02d}.")
        else:
            await message.reply("❌ Не удалось изменить время в планировщике, но настройка сохранена. Перезапустите бота.")

    # Start Polling
    logging.info("🚀 Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
