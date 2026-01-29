import asyncio
import websockets
import sys
import argparse
import json

URI = "ws://localhost:8000/ws"

async def run_mock_device(device_id: str):
    print(f"Connecting to {URI} as {device_id}...")
    try:
        async with websockets.connect(URI) as websocket:
            print("Connected to server!")
            
            # Initial state
            current_state = "OFF"
            
            # 1. Send Hello
            hello_msg = {
                "type": "device_hello",
                "device_id": device_id,
                "state": current_state
            }
            await websocket.send(json.dumps(hello_msg))
            print(f"Sent initial state: {json.dumps(hello_msg)}")

            while True:
                try:
                    message = await websocket.recv()
                    print(f"\n[Received]: {message}")
                    
                    try:
                        cmd_data = json.loads(message)
                    except json.JSONDecodeError:
                         print("Failed to decode JSON command")
                         continue

                    if cmd_data.get("type") == "sync_state":
                        new_state = cmd_data.get("state")
                        print(f"!!! Server Authority Sync !!! Setting state to: {new_state}")
                        current_state = new_state
                        
                    elif cmd_data.get("type") == "ping":
                        print("Ping received -> Sending Pong")
                        await websocket.send(json.dumps({"type": "pong"}))
                        
                    elif cmd_data.get("type") == "command":
                        action = cmd_data.get("action")
                        
                        if action == "TURN_ON":
                            print("Turning Light ON...")
                            current_state = "ON"
                            # Simulate processing time
                            await asyncio.sleep(0.5) 
                            
                            update_msg = {
                                "type": "state_update",
                                "device_id": device_id,
                                "state": current_state
                            }
                            await websocket.send(json.dumps(update_msg))
                            print(f"Sent confirmation: {json.dumps(update_msg)}")
                        
                        elif action == "TURN_OFF":
                            print("Turning Light OFF...")
                            current_state = "OFF"
                            # Simulate processing time
                            await asyncio.sleep(0.5)
                            
                            update_msg = {
                                "type": "state_update",
                                "device_id": device_id,
                                "state": current_state
                            }
                            await websocket.send(json.dumps(update_msg))
                            print(f"Sent confirmation: {json.dumps(update_msg)}")
                        
                        else:
                            print(f"Unknown action: {action}")
                    else:
                        print(f"Unknown message type: {cmd_data.get('type')}")

                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed by server.")
                    break
    except Exception as e:
        print(f"Failed to connect or connection error: {e}")
        print("Ensure the server is running (uvicorn main:app --reload)")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    parser = argparse.ArgumentParser(description="Mock ESP Device")
    parser.add_argument("--device-id", type=str, default="desk_light_1", help="Device ID for this emulator")
    args = parser.parse_args()

    try:
        asyncio.run(run_mock_device(args.device_id))
    except KeyboardInterrupt:
        print("\nMock device stopped.")

