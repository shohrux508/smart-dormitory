from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from typing import Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel
import asyncio

app = FastAPI(title="Smart Dormitory Desk Light")

# --- Data Models ---

class DeviceHello(BaseModel):
    type: str  # "device_hello"
    device_id: str
    state: str = "OFF" # Optional/Ignored by server v3

class SyncStateMessage(BaseModel):
    type: str = "sync_state"
    state: str

class StateUpdate(BaseModel):
    type: str  # "state_update"
    device_id: str
    state: str

class Command(BaseModel):
    type: str = "command"
    action: str

# --- Internal Device Model ---

class Device:
    def __init__(self, device_id: str, state: str = "OFF", status: str = "offline"):
        self.device_id = device_id
        self.state = state  # "ON" | "OFF"
        self.status = status  # "online" | "offline"
        self.last_seen: float = 0.0
        self.connection: Optional[WebSocket] = None

# --- Connection Manager ---

class ConnectionManager:
    def __init__(self):
        # device_id -> Device
        self.devices: Dict[str, Device] = {}

    def get_or_create_device(self, device_id: str) -> Device:
        if device_id not in self.devices:
            self.devices[device_id] = Device(device_id)
        return self.devices[device_id]

    async def connect(self, device_id: str, websocket: WebSocket):
        device = self.get_or_create_device(device_id)
        
        # 1. Register Connection
        device.connection = websocket
        device.status = "online"
        device.last_seen = datetime.now().timestamp()
        
        # 2. Server Authority: Enforce Server State
        # We ignore what the device sent in 'hello'.
        # We use the current state from memory (device.state).
        
        print(f"Device connected: {device_id}. Syncing to state: {device.state}")
        
        # 3. Send Sync Message
        sync_msg = SyncStateMessage(state=device.state)
        await websocket.send_text(sync_msg.model_dump_json())

    def disconnect(self, device_id: str):
        if device_id in self.devices:
            device = self.devices[device_id]
            device.connection = None
            device.status = "offline"
            print(f"Device disconnected: {device_id}")

    async def update_state(self, device_id: str, state: str):
        if device_id in self.devices:
            self.devices[device_id].state = state
            self.devices[device_id].last_seen = datetime.now().timestamp()
            print(f"State updated for {device_id}: {state}")

    def get_connection(self, device_id: str) -> Optional[WebSocket]:
        if device_id in self.devices:
            return self.devices[device_id].connection
        return None

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)
        
    def list_devices(self) -> List[dict]:
        return [
            {
                "device_id": d.device_id,
                "state": d.state,
                "status": d.status
            }
            for d in self.devices.values()
        ]

    async def run_heartbeat(self):
        print("Heartbeat loop started")
        while True:
            await asyncio.sleep(5)
            now = datetime.now().timestamp()
            # Copy items to avoid modification during iteration if disconnected
            for device_id, device in list(self.devices.items()):
                if device.status == "online":
                    # Check for timeout (15s)
                    if now - device.last_seen > 15:
                        print(f"Device {device_id} timed out (Last seen: {now - device.last_seen:.1f}s ago)")
                        self.disconnect(device_id)
                        continue

                    if device.connection:
                        try:
                            await device.connection.send_json({"type": "ping"})
                        except Exception as e:
                            print(f"Failed to ping {device_id}: {e}")
                            self.disconnect(device_id)

manager = ConnectionManager() # Created before logic using it

# --- Startup ---

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(manager.run_heartbeat())

# --- In-Memory State (Legacy/Transition) ---
# Old globals are removed in favor of `manager`. 
# Existing endpoints will break until Ticket 2/3 fix them. 
# But to keep file parseable we removed them.


@app.get("/")
async def root():
    """Проверка работы сервера."""
    return {
        "service": "Smart Dormitory Desk Light API",
        "devices_connected": len(manager.list_devices())
    }


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
            # If not valid JSON or not DeviceHello, close connection
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
                # Handle Pong
                if '"type": "pong"' in data or '"type":"pong"' in data:
                     # Simple check to avoid full parse if possible, or we can try parse
                     # But we need to update last_seen
                     if device_id in manager.devices:
                         manager.devices[device_id].last_seen = datetime.now().timestamp()
                     continue

                update_data = StateUpdate.model_validate_json(data)
                if update_data.type == "state_update" and update_data.device_id == device_id:
                     await manager.update_state(device_id, update_data.state)
                else:
                    print(f"Ignored invalid update from {device_id}")
            except Exception as e:
                # If json is valid but not StateUpdate (maybe Pong json object)
                # Let's try to see if it was pong via validation error? 
                # Better: parse as generic dict first
                print(f"Error processing message from {device_id}: {e}")
                # We optionally continue or break. Let's continue.

    except WebSocketDisconnect:
        if device_id:
            manager.disconnect(device_id)
    except Exception as e:
        print(f"Unexpected error with {device_id}: {e}")
        if device_id:
             manager.disconnect(device_id)


# --- HTTP API ---

@app.get("/api/devices")
async def list_devices():
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
    """Включить устройство (Optimistic Update)."""
    device = manager.get_or_create_device(device_id) 
    # v3: We can control even never-seen devices if we want, or just known ones.
    # Specs imply controlling known 'offline' devices.
    # get_or_create allows pre-provisioning.
    
    # 1. Update Server Authority State
    device.state = "ON"
    
    # 2. Try to send if Online
    if device.status == "online" and device.connection:
        command = Command(action="TURN_ON")
        try:
            await device.connection.send_text(command.model_dump_json())
            return {"device_id": device_id, "status": "command_sent", "state": "ON"}
        except Exception as e:
            print(f"Failed to send command to {device_id}: {e}")
            manager.disconnect(device_id)
            # Fallthrough to optimistic response
            
    return {"device_id": device_id, "status": "queued_optimistic", "state": "ON"}

@app.post("/api/devices/{device_id}/turn_off")
async def turn_device_off(device_id: str):
    """Выключить устройство (Optimistic Update)."""
    device = manager.get_or_create_device(device_id)
    
    # 1. Update Server Authority State
    device.state = "OFF"
    
    # 2. Try to send if Online
    if device.status == "online" and device.connection:
        command = Command(action="TURN_OFF")
        try:
            await device.connection.send_text(command.model_dump_json())
            return {"device_id": device_id, "status": "command_sent", "state": "OFF"}
        except Exception as e:
            print(f"Failed to send command to {device_id}: {e}")
            manager.disconnect(device_id)
            # Fallthrough to optimistic response
            
    return {"device_id": device_id, "status": "queued_optimistic", "state": "OFF"}

