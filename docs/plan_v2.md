# SMART-DORMITORY: Multi-Device Support Implementation Plan

## Goal
Update the system to support multiple devices (desk lights) connected simultaneously, identified by `device_id`, as per `specs_v2.md`.

## User Review Required
> [!IMPORTANT]
> This is a breaking change for existing clients (mock_esp.py) due to protocol changes (JSON instead of raw strings).

## Proposed Changes (Tickets)

### Ticket 1: Define Data Models & Connection Manager
**Goal**: Create a robust structure to manage multiple connections.
- **File**: `main.py`
- **Tasks**:
    1.  Define Pydantic models for protocol messages:
        - `DeviceHello` (type="device_hello", device_id, state)
        - `StateUpdate` (type="state_update", device_id, state)
        - `Command` (type="command", action)
    2.  Create `ConnectionManager` class:
        - `active_connections: Dict[str, WebSocket]`
        - `device_states: Dict[str, str]` (store limits/states)
        - Methods: `connect`, `disconnect`, `get_connection`, `update_state`, `list_devices`.

### Ticket 2: Update WebSocket Endpoint
**Goal**: Switch to JSON protocol and use Connection Manager.
- **File**: `main.py`
- **Tasks**:
    1.  Update `websocket_endpoint`:
        - Accept connection.
        - Wait for `DeviceHello` JSON.
        - Validate `device_id` and register in `ConnectionManager`.
        - Enforce `device_id` uniqueness (reject if already connected).
        - Loop for `StateUpdate` messages.
        - Handle disconnect cleanly.

### Ticket 3: Implement New HTTP API
**Goal**: Expose control for specific devices.
- **File**: `main.py`
- **Tasks**:
    1.  `GET /api/devices` -> Login to return list of keys from Manager.
    2.  `GET /api/devices/{device_id}` -> Return state from Manager.
    3.  `POST /api/devices/{device_id}/turn_on` -> Find WS, send `{"type": "command", "action": "TURN_ON"}`.
    4.  `POST /api/devices/{device_id}/turn_off` -> Find WS, send `{"type": "command", "action": "TURN_OFF"}`.
    5.  Remove old single-device endpoints (`/api/light/on`, etc.).

### Ticket 4: Update Mock ESP (Emulator)
**Goal**: Make the emulator compatible with the new protocol.
- **File**: `mock_esp.py`
- **Tasks**:
    1.  Add CLI argument `--device-id` (default: "desk_light_1").
    2.  Update `run_mock_device`:
        - Send `DeviceHello` JSON on connect.
        - Send `StateUpdate` JSON on change.
        - Handle `Command` JSON from server.

### Ticket 5: Update & Expand Tests
**Goal**: Verify multi-device logic.
- **File**: `test_main.py`
- **Tasks**:
    1.  Update `test_websocket_connect` to send valid JSON hello.
    2.  Add `test_list_devices`.
    3.  Add `test_device_isolation` (connect device A, ensure device B commands fail).
    4.  Verify full flow: Connect -> Hello -> List -> API Command -> Device Update -> API State.

## Verification Plan

### Automated Tests
Run `pytest` to execute `test_main.py`.
```powershell
pytest
```

### Manual Verification
1.  **Start Server**: `uvicorn main:app --reload`
2.  **Start Emulator 1**: `python mock_esp.py --device-id device_1`
3.  **Start Emulator 2**: `python mock_esp.py --device-id device_2`
4.  **Check List**: Curl or Browser `http://127.0.0.1:8000/api/devices` -> Should see both.
5.  **Control Device 1**: Send POST to turn ON device 1. Verify only Device 1 logs "Turned ON".
6.  **Control Device 2**: Send POST to turn ON device 2. Verify only Device 2 logs "Turned ON".
