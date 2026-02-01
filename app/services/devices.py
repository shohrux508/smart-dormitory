import asyncio
from typing import Optional, Dict, List
from datetime import datetime
from fastapi import WebSocket
from pydantic import BaseModel


from app.services.telegram_bot import notify_all_users




class DeviceHello(BaseModel):
    type: str  # "device_hello"
    device_id: str
    state: str = "OFF"

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
        # Dashboard clients
        self.clients: List[WebSocket] = []

    async def connect_client(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.append(websocket)
        # Send initial state
        await websocket.send_json({
            "type": "full_state", 
            "devices": self.list_devices()
        })
        print(f"Client connected. Total clients: {len(self.clients)}")

    def disconnect_client(self, websocket: WebSocket):
        if websocket in self.clients:
            self.clients.remove(websocket)
            print(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message: dict):
        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                # We might want to remove dead clients here, but usually disconnect_client handles it
                pass

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
        print(f"Device connected: {device_id}. Syncing to state: {device.state}")
        
        # 3. Send Sync Message
        sync_msg = SyncStateMessage(state=device.state)
        await websocket.send_text(sync_msg.model_dump_json())

        # 4. Broadcast to clients
        await self.broadcast({
            "type": "device_connected",
            "device": {
                "device_id": device.device_id,
                "state": device.state,
                "status": "online"
            }
        })

    def disconnect(self, device_id: str):
        if device_id in self.devices:
            device = self.devices[device_id]
            device.connection = None
            device.status = "offline"
            print(f"Device disconnected: {device_id}")
            
            # Broadcast disconnect
            asyncio.create_task(self.broadcast({
                "type": "device_disconnected",
                "device_id": device_id
            }))

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

    # New helper for control
    async def send_command(self, device_id: str, action: str) -> bool:
        """
        Отправляет команду на устройство и обновляет локальное состояние.
        action: "TURN_ON" | "TURN_OFF"
        Returns: True если отправлено, False если офлайн
        """
        device = self.get_or_create_device(device_id)
        
        # Update Authority
        target_state = "ON" if action == "TURN_ON" else "OFF"
        device.state = target_state
        
        if device.status == "online" and device.connection:
            cmd = Command(action=action)
            try:
                await device.connection.send_text(cmd.model_dump_json())
                return True
            except Exception as e:
                print(f"Failed to send command to {device_id}: {e}")
                self.disconnect(device_id)
        
        return False

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

# Global Instance
manager = ConnectionManager()
