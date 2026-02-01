import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services.devices import manager, StateUpdate


client = TestClient(app)

@pytest.mark.asyncio
async def test_websocket_broadcast():
    """
    Simulates a dashboard client connecting to /ws/dashboard 
    and verifies it receives state updates from backend.
    """
    # 1. Start WebSocket connection (Client)
    # Note: TestClient used with 'with' block context manager handles startup/shutdown events
    # 1. Start WebSocket connection (Client)
    # Note: TestClient used with 'with' block context manager handles startup/shutdown events
    with client.websocket_connect("/ws/dashboard") as websocket:
        # Consume initial state
        websocket.receive_json()
        
        # 2. Simulate Device State Change (Backend)
        test_device_id = "test_lamp_01"
        test_state = "ON"
        
        # Manually trigger broadcast via devices manager 
        # (This mimics what happens inside devices.update_state or send_command)
        await manager.broadcast({
            "type": "state_change",
            "device_id": test_device_id,
            "state": test_state
        })
        
        # 3. Verify Client received the message
        data = websocket.receive_text()
        message = json.loads(data)
        
        assert message["type"] == "state_change"
        assert message["device_id"] == test_device_id
        assert message["state"] == test_state
