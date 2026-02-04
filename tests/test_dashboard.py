import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.devices import manager
from app.database import SessionLocal, TelegramBookmark

# Use a single client instance
client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_manager():
    manager.devices.clear()
    manager.clients.clear()
    yield

def test_dashboard_websocket_flow():
    device_id = "dashboard_test_dev"
    test_user_id = 777
    
    # Setup: Create bookmark
    db = SessionLocal()
    # Cleanup first
    db.query(TelegramBookmark).filter(TelegramBookmark.telegram_id == test_user_id).delete()
    
    bookmark = TelegramBookmark(telegram_id=test_user_id, device_id=device_id, custom_name="Test Device")
    db.add(bookmark)
    db.commit()
    db.close()
    
    try:
        # 1. Connect Dashboard WITH user_id
        with client.websocket_connect(f"/ws/dashboard?user_id={test_user_id}") as dashboard_ws:
            # 1.1 Receive Initial State
            init_msg = dashboard_ws.receive_json()
            assert init_msg["type"] == "full_state"
            assert init_msg["devices"] == []
            
            # 2. Connect Device using the same client
            with client.websocket_connect("/ws") as device_ws:
                device_ws.send_json({"type": "device_hello", "device_id": device_id, "state": "OFF"})
                device_ws.receive_json() # Consume sync_state
                
                # 3. Dashboard should receive device_connected
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
            
    finally:
        # Cleanup DB
        db = SessionLocal()
        db.query(TelegramBookmark).filter(TelegramBookmark.telegram_id == test_user_id).delete()
        db.commit()
        db.close()
