from fastapi.testclient import TestClient
from app.main import app
import pytest
from app.services.devices import manager

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_manager():
    # Clean up before each test
    manager.devices.clear()
    yield

def test_read_root():
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "devices_connected" in data

def test_list_devices_empty():
    response = client.get("/api/devices")
    assert response.status_code == 200
    assert response.json() == []

def test_get_device_not_found():
    response = client.get("/api/devices/non_existent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Device not found"

def test_websocket_flow_and_api():
    device_id = "test_device_1"
    
    with client.websocket_connect("/ws") as websocket:
        # 1. Send Hello
        hello_msg = {
            "type": "device_hello", 
            "device_id": device_id, 
            "state": "OFF"
        }
        websocket.send_json(hello_msg)
        
        # 1.1 Verify Server Authority: Receive Sync State
        sync_data = websocket.receive_json()
        assert sync_data["type"] == "sync_state"
        assert sync_data["state"] in ["ON", "OFF"] # Should be default OFF for new device
        assert sync_data["state"] == "OFF"

        # 2. Check API lists device
        response = client.get("/api/devices")
        assert response.status_code == 200
        devices = response.json()
        # Verify device_id is in the list of devices objects
        assert any(d["device_id"] == device_id for d in devices)
        
        # 3. Check specific device state
        response = client.get(f"/api/devices/{device_id}")
        assert response.status_code == 200
        assert response.json()["state"] == "OFF"
        
        # 4. Update state via WebSocket
        update_msg = {
            "type": "state_update",
            "device_id": device_id,
            "state": "ON"
        }
        websocket.send_json(update_msg)
        
        # 5. Check API reflects update
        response = client.get(f"/api/devices/{device_id}")
        assert response.status_code == 200
        assert response.json()["state"] == "ON"
        
        # 6. Send Command via API
        response = client.post(f"/api/devices/{device_id}/turn_off")
        assert response.status_code == 200
        assert response.json()["status"] == "command_sent"
        
        # 7. Verify WebSocket received command
        data = websocket.receive_json()
        assert data["type"] == "command"
        assert data["action"] == "TURN_OFF"

def test_two_devices_isolation():
    dev1 = "dev_1"
    dev2 = "dev_2"
    
    # We use nested context managers to simulate two connections
    with client.websocket_connect("/ws") as ws1:
        ws1.send_json({"type": "device_hello", "device_id": dev1, "state": "OFF"})
        # Consume sync
        assert ws1.receive_json()["type"] == "sync_state"
        
        with client.websocket_connect("/ws") as ws2:
            ws2.send_json({"type": "device_hello", "device_id": dev2, "state": "ON"})
            # Consume sync
            assert ws2.receive_json()["type"] == "sync_state"
            
            # Check List
            response = client.get("/api/devices")
            devices = response.json()
            assert any(d["device_id"] == dev1 for d in devices)
            assert any(d["device_id"] == dev2 for d in devices)
            assert len(devices) >= 2
            
            # Send command to Dev 1
            client.post(f"/api/devices/{dev1}/turn_on")
            
            # Dev 1 should receive it
            msg1 = ws1.receive_json()
            assert msg1["action"] == "TURN_ON"
            
            # Dev 2 check
            resp2 = client.get(f"/api/devices/{dev2}")
            # Server defaults new devices to OFF, ignoring the "ON" in Hello
            assert resp2.json()["state"] == "OFF"

def test_reconnect_preserves_server_state():
    device_id = "reconnect_test"
    
    # Phase 1: Connect, switch ON, disconnect
    with client.websocket_connect("/ws") as ws:
        # Hello
        ws.send_json({"type": "device_hello", "device_id": device_id, "state": "OFF"})
        # Consume sync
        ws.receive_json()
        # Switch ON via API
        client.post(f"/api/devices/{device_id}/turn_on")
        # Verify state
        assert client.get(f"/api/devices/{device_id}").json()["state"] == "ON"
    
    # Phase 2: Reconnect (Simulate restart with OFF state)
    with client.websocket_connect("/ws") as ws:
        # Try to say "I am OFF"
        ws.send_json({"type": "device_hello", "device_id": device_id, "state": "OFF"})
        
        # Server verification: Should reply with "ON" because server is authority
        sync_msg = ws.receive_json()
        assert sync_msg["type"] == "sync_state"
        assert sync_msg["state"] == "ON" 

def test_api_updates_offline_device():
    device_id = "offline_dev"
    
    # 1. Update offline device (Optimistic UI)
    response = client.post(f"/api/devices/{device_id}/turn_on")
    assert response.status_code == 200
    assert response.json()["status"] == "queued_optimistic"
    assert response.json()["state"] == "ON"
    
    # 2. Check State via GET
    response = client.get(f"/api/devices/{device_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "ON"
    assert data["status"] == "offline"
    
    # 3. Connect device -> Should receive Sync ON
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "device_hello", "device_id": device_id, "state": "OFF"})
        
        sync_msg = ws.receive_json()
        assert sync_msg["state"] == "ON"
