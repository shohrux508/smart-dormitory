
import os
import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

import database

# Fixed time for daily message (default if not in DB)
DEFAULT_TIME_HOUR = 9
DEFAULT_TIME_MINUTE = 0

_scheduler = None

async def send_daily_message(bot: Bot):
    """Job to send daily task assignment."""
    group_id = os.getenv("GROUP_ID")
    if not group_id:
        logging.warning("⚠️ GROUP_ID not set. Skipping daily message.")
        return

    users = await database.get_users()
    if not users:
        logging.info("ℹ️ No users to assign task to.")
        return

    # Deterministic rotation
    # Use day of year to cycle through users
    day_of_year = datetime.now().timetuple().tm_yday
    user_index = day_of_year % len(users)
    target_user = users[user_index]

    # Format message
    # 📅 Понедельник, 29
    # 👤 Иван
    # 📝 Уборка комнаты
    
    # Simple russian date formatting
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    now = datetime.now()
    weekday_str = days[now.weekday()]
    date_str = now.strftime("%d.%m")
    
    task_text = target_user['user_task'] if target_user['user_task'] else "Таск не назначен"
    
    message_text = (
        f"📅 {weekday_str}, {date_str}\n"
        f"👤 {target_user['full_name']}\n"
        f"📝 {task_text}"
    )

    try:
        await bot.send_message(chat_id=group_id, text=message_text)
        logging.info(f"✅ Daily message sent to {group_id}.")
    except Exception as e:
        logging.error(f"❌ Failed to send daily message: {e}")

async def reschedule_daily_message(hour: int, minute: int, bot: Bot):
    """Reschedule the daily job to a new time."""
    if _scheduler:
        try:
            # ID 'daily_job' must match what we used when adding it
            _scheduler.reschedule_job('daily_job', trigger='cron', hour=hour, minute=minute)
            logging.info(f"🔄 Rescheduled daily job to {hour:02d}:{minute:02d}")
            return True
        except Exception as e:
            logging.error(f"❌ Failed to reschedule: {e}")
            return False
    return False

async def start_scheduler(bot: Bot):
    """Initialize and start the scheduler."""
    global _scheduler
    _scheduler = AsyncIOScheduler()
    
    # Load time from DB or use default
    time_setting = await database.get_setting("daily_time")
    if time_setting:
        try:
            h, m = map(int, time_setting.split(":"))
            hour, minute = h, m
        except ValueError:
            hour, minute = DEFAULT_TIME_HOUR, DEFAULT_TIME_MINUTE
    else:
        hour, minute = DEFAULT_TIME_HOUR, DEFAULT_TIME_MINUTE

    logging.info(f"⏰ Scheduling daily message at {hour:02d}:{minute:02d}")

    # Schedule daily job with ID for easier updates
    _scheduler.add_job(
        send_daily_message, 
        'cron', 
        hour=hour, 
        minute=minute, 
        args=[bot],
        id='daily_job',
        replace_existing=True
    )
    
    _scheduler.start()
    logging.info("⏰ Scheduler started.")
