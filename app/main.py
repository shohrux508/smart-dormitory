from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from typing import Optional, Dict, List
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel

import logging
from app.config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импорт основных компонентов
from app.services.devices import manager, DeviceHello, StateUpdate, Command, Device

# Импорт сервиса Алисы
from app.routers.alice import router as alice_router

# Импорт БД
# User и DeviceMeta удалены
from app.database import engine, Base, get_db
import app.services.telegram_bot as tg_bot

from contextlib import asynccontextmanager

# Создаем таблицы БД (если их нет)
# Это важно для первого запуска на новом сервере (Deploy)
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запускаем фоновую задачу heartbeat
    task = asyncio.create_task(manager.run_heartbeat())
    # Запускаем Телеграм бота
    bot_task = asyncio.create_task(tg_bot.start_bot())
    
    yield
    
    # При выключении можно отменить задачу, если нужно
    await tg_bot.stop_bot()
    task.cancel()
    # bot_task will be cancelled/stopped by stop_bot logic usually, or we can cancel it
    bot_task.cancel()

app = FastAPI(title="Smart Dormitory Desk Light", lifespan=lifespan)

# Подключаем роутер Алисы (без префикса, так как тесты ожидают /authorize и /v1.0 в корне)
app.include_router(alice_router)
@app.get("/status")
async def root():
    """Проверка работы сервера."""
    return {
        "service": "Smart Dormitory Desk Light API",
        "devices_connected": len(manager.list_devices())
    }

# --- Root Endpoint (Health Check) ---
# Для проверки работоспособности (Railway Check)
@app.get("/")
async def health_check():
    return {
        "status": "ok", 
        "service": "Smart Dormitory API",
        "doc": "Go to /docs for API documentation or open static/index.html manually if needed."
    }

# StaticFiles mount moved to end of file to avoid shadowing API routes


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    device_id = None
    
    try:
        # 1. Wait for Hello Message
        data = await websocket.receive_text()
        try:
            hello_data = DeviceHello.model_validate_json(data)
        except Exception:
            await websocket.close(code=1008, reason="Invalid Hello Message")
            return

        if hello_data.type != "device_hello":
             await websocket.close(code=1008, reason="Expected device_hello")
             return

        device_id = hello_data.device_id
        
        # 2. Register Connection
        if manager.get_connection(device_id):
             await websocket.close(code=1008, reason="Device ID already connected")
             return
             
        await manager.connect(device_id, websocket)
        
        # 3. Listen for Updates
        while True:
            data = await websocket.receive_text()
            try:
                # Handle Pong (simple text check or json parse)
                if '"type": "pong"' in data or '"type":"pong"' in data:
                     if device_id in manager.devices:
                         manager.devices[device_id].last_seen = datetime.now().timestamp()
                     continue

                update_data = StateUpdate.model_validate_json(data)
                if update_data.type == "state_update" and update_data.device_id == device_id:
                     await manager.update_state(device_id, update_data.state)
                else:
                    logger.warning(f"Ignored invalid update from {device_id}")
            except Exception as e:
                logger.error(f"Error processing message from {device_id}: {e}")
                pass # Continue listening

    except WebSocketDisconnect:
        if device_id:
            manager.disconnect(device_id)
    except Exception as e:
        logger.error(f"Unexpected error with {device_id}: {e}")
        if device_id:
             manager.disconnect(device_id)


# --- HTTP API (Legacy / Direct Control) ---

@app.get("/api/devices")
async def list_devices_api():
    """Список всех подключенных устройств."""
    return manager.list_devices()

@app.get("/api/devices/{device_id}")
async def get_device_state(device_id: str):
    """Получить состояние конкретного устройства."""
    device = manager.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return {
        "device_id": device.device_id,
        "state": device.state,
        "status": device.status
    }

@app.post("/api/devices/{device_id}/turn_on")
async def turn_device_on(device_id: str):
    """Включить устройство."""
    sent = await manager.send_command(device_id, "TURN_ON")
    status = "command_sent" if sent else "queued_optimistic"
    return {"device_id": device_id, "status": status, "state": "ON"}

@app.post("/api/devices/{device_id}/turn_off")
async def turn_device_off(device_id: str):
    """Выключить устройство."""
    sent = await manager.send_command(device_id, "TURN_OFF")
    status = "command_sent" if sent else "queued_optimistic"
    return {"device_id": device_id, "status": status, "state": "OFF"}

# --- Device Settings API ---

class DeviceSettings(BaseModel):
    name: str
    room: str

@app.put("/api/devices/{device_id}/settings")
async def update_device_settings(
    device_id: str, 
    settings: DeviceSettings, 
    db: Session = Depends(get_db)
):
    """
    Установить имя и комнату для устройства.
    NOTE: В новой версии без аккаунтов этот эндпоинт пока отключен/урезан,
    так как настройки хранятся в TelegramBookmarks, а здесь нет user context.
    В будущем можно передавать telegram_id или токен авторизации.
    """
    # TODO: Реализовать логику для TelegramBookmark if authorization header is present
    return {"status": "error", "message": "Settings update only available via Telegram Bot or Alice context"}

# --- Debug Catch-All for WebSockets ---
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket, user_id: Optional[int] = None):
    # If user_id is provided in query params (e.g. ?user_id=123), use it for filtering
    # Ideally verify this with a token, but for MVP we trust the query param or Telegram WebApp context
    await manager.connect_client(websocket, user_id)
    try:
        while True:
            # Keep connection alive, maybe handle ping/pong if needed
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect_client(websocket)
    except Exception as e:
        logger.error(f"Dashboard client error: {e}")
        manager.disconnect_client(websocket)

# --- Debug Catch-All for WebSockets ---
@app.websocket("/{path:path}")
async def websocket_catchall(websocket: WebSocket, path: str):
    logger.warning(f"⚠️ Caught stray WebSocket connection to path: /{path}")
    await websocket.accept()
    await websocket.send_text("Invalid WebSocket Path. Use /ws or /ws/dashboard")
    await websocket.close(code=1008)

# --- Static Files (Dashboard) ---
# --- Static Files (Dashboard) ---
# Mount static files at /dashboard to avoid conflict with root health check
app.mount("/dashboard", StaticFiles(directory="static", html=True), name="static")
