from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "state" in data
    assert "device_connected" in data

def test_initial_state():
    response = client.get("/api/light/state")
    assert response.status_code == 200
    assert response.json()["state"] == "UNKNOWN"

def test_command_without_device():
    # Should fail as no device is connected in this test context
    response = client.post("/api/light/on")
    assert response.status_code == 503
    assert response.json()["detail"] == "Device not connected"

# Note: Testing WebSocket properly often requires async tests or different tooling (TestClient supports websocket context manager).
# Here is a basic websocket connection test.

def test_websocket_connect():
    with client.websocket_connect("/ws") as websocket:
        # Send initial state
        websocket.send_text("STATE:ON")
        
        # Check HTTP state reflects this (in a real async server scenario sharing memory)
        # However, TestClient creates a thread/loop context that might share state if configured right.
        # Let's verify if TestClient shares the same app instance memory.
        
        response = client.get("/api/light/state")
        assert response.status_code == 200
        assert response.json()["state"] == "ON"
        assert response.json()["device_connected"] is True

        # Test receiving command via HTTP triggering WebSocket message
        # This is tricky in synchronous TestClient flow because standard TestClient calls block.
        # For simple robust testing, we rely on the above verify that state updates work.
