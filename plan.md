# 📋 Implementation Plan: Reliability Layer (v3)

**Goal**: Implement Server Authority, Heartbeat (Ping/Pong), and Optimistic API as per `specs_v3.md`.

## 🛠 Tickets

### Ticket 1: Update Device Model & Store
**Description**: Update the internal state representation of a device.
- **Tasks**:
    1.  Modify in-memory store structure to hold `Device` objects instead of simple dicts/IDs.
    2.  Add fields:
        -   `state`: "ON" | "OFF" (default "OFF")
        -   `status`: "online" | "offline"
        -   `last_seen`: timestamp (float)
        -   `connection`: WebSocket object (nullable)
- **Verification**: `main.py` syntax check.

### Ticket 2: Implement Server Authority Handshake
**Description**: Change the `hello` flow. Server dictates state.
- **Tasks**:
    1.  On `device_hello`, **do not** update `state` from message.
    2.  Immediately send `{"type": "sync_state", "state": <current_server_state>}` to the device.
    3.  Mark device as `status="online"`.
- **Verification**:
    -   Run `test_main.py` (will fail initially).
    -   Update `test_websocket_flow_and_api` to expect `sync_state` message after hello.

### Ticket 3: Implement Heartbeat Sender (Ping)
**Description**: Server sends PING every 5s.
- **Tasks**:
    1.  Create a background task `heartbeat_loop()` using `asyncio.create_task` on startup.
    2.  Loop forever (while server runs):
        -   Sleep 5s.
        -   Iterate over all `online` devices.
        -   Send `{"type": "ping"}`.
        -   Handle connection errors (mark offline if send fails).
- **Verification**: Log check "Sending ping to..."

### Ticket 4: Implement Pong Handler & Watchdog
**Description**: Handle PONG responses and disconnect dead devices (Timeout 15s).
- **Tasks**:
    1.  Handle `{"type": "pong"}`: Update `last_seen = time.time()`.
    2.  In `heartbeat_loop`, check: `if time.time() - device.last_seen > 15`:
        -   Close connection (if open).
        -   Mark `status="offline"`.
        -   Log "Device disconnected (timeout)".
- **Verification**: Manually connect, wait 20s without sending pong, verify log/status.

### Ticket 5: Optimistic API Updates
**Description**: Allow controlling offline devices.
- **Tasks**:
    1.  `POST /api/devices/{id}/turn_on`:
        -   Find device in memory.
        -   Update `state = "ON"`.
        -   If `status == "online"`, send WebSocket command.
        -   If `status == "offline"`, just return 200 OK.
    2.  `GET /api/devices/`
        -   Return full structure with `state` and `status`.
- **Verification**:
    -   Test: Call API for offline device -> 200 OK.
    -   Connect device -> Expect `sync_state` with new value.

### Ticket 6: Update & Expand Tests
**Description**: Fix existing tests and add new scenarios.
- **Tasks**:
    1.  Fix `test_websocket_flow_and_api` matches new protocol (Sync).
    2.  Add `test_reconnect_preserves_server_state`:
        -   Connect (State OFF) -> API Turn ON -> Disconnect.
        -   Connect again -> Expect Sync ON.
    3.  Add `test_api_updates_offline_device`:
        -   Device Offline -> API Turn ON (200 OK).
        -   Check GET state is ON.
- **Verification**: `pytest` passes.

## 🧪 Verification Plan

### Automated
Run `pytest` to verify all updated logic.
```bash
pytest test_main.py
```

### Manual
1.  Run server: `python main.py` OR `uvicorn main:app --reload`
2.  Use `mock_esp.py` (need to update it to support PING/PONG and SYNC):
    -   Verify it automatically responds to PING with PONG.
    -   Verify it accepts SYNC_STATE.
    -   Kill `mock_esp.py` -> Wait 15s -> Check API `GET /devices` shows `offline`.
    -   Restart `mock_esp.py` -> Check it syncs to correct state.
