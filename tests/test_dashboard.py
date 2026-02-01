import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.devices import manager

# Create separate clients to potentially avoid single-session blocking
dashboard_client = TestClient(app)
device_client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_manager():
    manager.devices.clear()
    manager.clients.clear()
    yield

def test_dashboard_websocket_flow():
    device_id = "dashboard_test_dev"
    
    # 1. Connect Dashboard
    with dashboard_client.websocket_connect("/ws/dashboard") as dashboard_ws:
        # 1.1 Receive Initial State
        init_msg = dashboard_ws.receive_json()
        assert init_msg["type"] == "full_state"
        assert init_msg["devices"] == []
        
        # 2. Connect Device using secondary client
        with device_client.websocket_connect("/ws") as device_ws:
            device_ws.send_json({"type": "device_hello", "device_id": device_id, "state": "OFF"})
            device_ws.receive_json() # Consume sync_state
            
            # 3. Dashboard should receive device_connected
            # Ideally this shouldn't block if the buffer is fine
            dash_msg = dashboard_ws.receive_json()
            assert dash_msg["type"] == "device_connected"
            assert dash_msg["device"]["device_id"] == device_id
            assert dash_msg["device"]["status"] == "online"
            
            # 4. Update Device State
            device_ws.send_json({"type": "state_update", "device_id": device_id, "state": "ON"})
            
            # 5. Dashboard should receive state_change
            dash_msg = dashboard_ws.receive_json()
            assert dash_msg["type"] == "state_change"
            assert dash_msg["device_id"] == device_id
            assert dash_msg["state"] == "ON"
            
        # 6. Device Disconnects
        # Dashboard should receive device_disconnected
        dash_msg = dashboard_ws.receive_json()
        assert dash_msg["type"] == "device_disconnected"
        assert dash_msg["device_id"] == device_id
