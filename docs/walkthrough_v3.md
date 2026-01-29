# 🚶‍♂️ Smart Dormitory - Walkthrough Guide

## 🌟 Overview
This project implements a **Reliable Desk Light Control System** using WebSocket and FastAPI.
Version: **v3 (Reliability Layer)**.

Key Features:
- **Server Authority**: The server is the single source of truth.
- **Heartbeat**: Auto-detection of dead connections (Ping/Pong).
- **Optimistic API**: Control your devices even when they are offline.

---

## 🚀 Quick Start

### 1. Setup Environment
```bash
# Windows (PowerShell)
python -m venv shvenv
.\shvenv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the Server
Start the backend server. It hosts the API and WebSocket handler.
```bash
uvicorn main:app --reload
```
*Server runs at: `http://127.0.0.1:8000`*
*API Docs: `http://127.0.0.1:8000/docs`*

### 3. Run a Mock Device
Open a **new terminal** and run the emulated ESP32 device.
```bash
python mock_esp.py --device-id "my_lamp_1"
```
You should see:
> `Connected to server!`
> `!!! Server Authority Sync !!! Setting state to: OFF`
> `Ping received -> Sending Pong` (every 5s)

---

## 🧪 Verification Scenarios

### Scenario A: Basic Control
1.  Open Swagger UI: `http://127.0.0.1:8000/docs`
2.  Find **POST /api/devices/{device_id}/turn_on**.
3.  Execute for `my_lamp_1`.
4.  **Check Mock Terminal**: "Turning Light ON..."
5.  **Check API**: returns `status: "command_sent"`.

### Scenario B: Server Authority (The "Power Cut" Test)
1.  Turn the light **ON** via API.
2.  **Kill the Mock Device** (Ctrl+C).
3.  **Restart the Mock Device** (`python mock_esp.py ...`).
4.  **Observe**: The device immediately switches **ON** (Sync received from server).
    *   *Why?* The server remembered the state while the device was gone.

### Scenario C: Offline Control (Optimistic UI)
1.  **Kill the Mock Device**.
2.  Wait 15 seconds (Server log: `Device my_lamp_1 timed out`).
3.  Go to API and call **POST /turn_off**.
4.  **Response**: `200 OK`, `status: "queued_optimistic"`.
5.  **Restart the Mock Device**.
6.  **Observe**: It immediately syncs to **OFF**.

---

## ✅ Running Tests
Run the integration test suite to verify all logic automatically.
```bash
pytest test_main.py
```
