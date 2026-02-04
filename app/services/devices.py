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
        # Dashboard clients: WebSocket -> Set[device_id] (whitelist of devices to receive updates for)
        # If set is None or empty, it might mean "all" for superadmin, but let's assume strict filtering for users.
        # However, for backward compatibility or direct access without user_id, we can allow all.
        # Let's use: WebSocket -> Optional[Set[str]]
        # None = All devices (legacy/admin)
        # Set = Only specific devices
        self.clients: Dict[WebSocket, Optional[set]] = {}

    async def connect_client(self, websocket: WebSocket, user_id: Optional[int] = None):
        await websocket.accept()
        
        # Use simple logic:
        # If user_id provided: Show ONLY bookmarks.
        # If user_id NOT provided: Show NOTHING (Secure default).
        # To see devices, the user MUST be identified.
        
        allowed_devices = {} # Default: Empty / Access Denied (Map: device_id -> custom_name)
        
        if user_id:
            # Query DB for bookmarks
            from app.database import SessionLocal, TelegramBookmark
            db = SessionLocal()
            try:
                bookmarks = db.query(TelegramBookmark).filter(TelegramBookmark.telegram_id == user_id).all()
                for b in bookmarks:
                    allowed_devices[b.device_id] = b.custom_name or b.device_id
                    
                print(f"Client {user_id} connected. Allowed devices: {list(allowed_devices.keys())}")
            except Exception as e:
                print(f"Error fetching bookmarks for {user_id}: {e}")
                # allowed_devices remains empty
            finally:
                db.close()
        else:
             print("Client connected without user_id. Access restricted to 0 devices.")
        
        # Store just keys for filtering in broadcast, but we might need names later?
        # Actually broadcast doesn't personalize names per user easily in a loop efficiently.
        # But for initial state we can send names.
        self.clients[websocket] = set(allowed_devices.keys())
        
        # Send initial state (Filtered & Enriched with Names)
        all_devices = self.list_devices()
        
        final_list = []
        if allowed_devices:
             for d in all_devices:
                 d_id = d["device_id"]
                 if d_id in allowed_devices:
                     # Create copy to avoid mutating global/other users state if we were caching
                     d_copy = d.copy()
                     d_copy["name"] = allowed_devices[d_id] # Inject Custom Name
                     final_list.append(d_copy)
        
        await websocket.send_json({
            "type": "full_state", 
            "devices": final_list
        })
        print(f"Client connected. Total clients: {len(self.clients)}")

    def disconnect_client(self, websocket: WebSocket):
        if websocket in self.clients:
            del self.clients[websocket]
            print(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message: dict):
        target_device_id = message.get("device_id") or (message.get("device", {}).get("device_id") if "device" in message else None)
        
        for client, allowed in self.clients.items():
            # Filter logic
            if target_device_id and allowed is not None:
                if target_device_id not in allowed:
                    continue
            
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
            
            # Broadcast state change to dashboard
            asyncio.create_task(self.broadcast({
                "type": "state_change",
                "device_id": device_id,
                "state": state
            }))

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
