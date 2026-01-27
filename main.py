from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from typing import Optional
from datetime import datetime

app = FastAPI(title="Smart Dormitory Desk Light")

# --- In-Memory State ---
# Храним состояние света: 'ON', 'OFF' или 'UNKNOWN'
last_known_state: str = "UNKNOWN"
last_received_at: Optional[datetime] = None

# Активное WebSocket соединение с ESP
# Политикой "Один сервер - Одно устройство" мы разрешаем только одно активное подключение.
active_websocket: Optional[WebSocket] = None

@app.get("/")
async def root():
    """Проверка работы сервера."""
    return {
        "service": "Smart Dormitory Desk Light API",
        "state": last_known_state,
        "device_connected": active_websocket is not None
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global active_websocket, last_known_state, last_received_at
    
    # 1. Enforce Single Connection Policy
    if active_websocket is not None:
        await websocket.close(code=1008, reason="Device already connected")
        return

    # 2. Accept connection
    await websocket.accept()
    active_websocket = websocket
    print(f"Device connected: {websocket.client}")

    try:
        while True:
            # 3. Receive messages
            data = await websocket.receive_text()
            last_received_at = datetime.now()
            
            # Simple Protocol Processor
            if data == "STATE:ON":
                last_known_state = "ON"
                print("State updated: ON")
            elif data == "STATE:OFF":
                last_known_state = "OFF"
                print("State updated: OFF")
            else:
                print(f"Unknown message received: {data}")

    except WebSocketDisconnect:
        # 4. Handle Disconnect
        print("Device disconnected")
        active_websocket = None
        last_known_state = "UNKNOWN"
    except Exception as e:
        print(f"Error: {e}")
        active_websocket = None
        last_known_state = "UNKNOWN"

# --- HTTP API ---

@app.get("/api/light/state")
async def get_light_state():
    """Получить текущее состояние света."""
    return {
        "state": last_known_state,
        "last_received_at": last_received_at,
        "device_connected": active_websocket is not None
    }

@app.post("/api/light/on")
async def turn_light_on():
    """Отправить команду включения света."""
    global active_websocket
    if active_websocket is None:
        raise HTTPException(status_code=503, detail="Device not connected")
    
    try:
        await active_websocket.send_text("ON")
        return {"status": "command_sent", "command": "ON"}
    except Exception as e:
         active_websocket = None
         raise HTTPException(status_code=500, detail=f"Failed to send command: {str(e)}")

@app.post("/api/light/off")
async def turn_light_off():
    """Отправить команду выключения света."""
    global active_websocket
    if active_websocket is None:
        raise HTTPException(status_code=503, detail="Device not connected")
    
    try:
        await active_websocket.send_text("OFF")
        return {"status": "command_sent", "command": "OFF"}
    except Exception as e:
         active_websocket = None
         raise HTTPException(status_code=500, detail=f"Failed to send command: {str(e)}")
