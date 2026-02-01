import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services.devices import manager, StateUpdate
from app.services.connection_manager import dashboard_manager

client = TestClient(app)

@pytest.mark.asyncio
async def test_websocket_broadcast():
    """
    Simulates a dashboard client connecting to /ws/dashboard 
    and verifies it receives state updates from backend.
    """
    # 1. Start WebSocket connection (Client)
    # Note: TestClient used with 'with' block context manager handles startup/shutdown events
    with client.websocket_connect("/ws/dashboard") as websocket:
        
        # 2. Simulate Device State Change (Backend)
        test_device_id = "test_lamp_01"
        test_state = "ON"
        
        # Manually trigger broadcast via devices manager 
        # (This mimics what happens inside devices.update_state or send_command)
        update_msg = StateUpdate(type="state_update", device_id=test_device_id, state=test_state)
        await dashboard_manager.broadcast(update_msg.model_dump_json())
        
        # 3. Verify Client received the message
        data = websocket.receive_text()
        message = json.loads(data)
        
        assert message["type"] == "state_update"
        assert message["device_id"] == test_device_id
        assert message["state"] == test_state
