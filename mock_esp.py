import asyncio
import websockets
import json
import argparse
import sys

# Protocol Config
SERVER_URI = "ws://127.0.0.1:8000/ws"

async def device_client(device_id):
    uri = SERVER_URI
    print(f"Connecting to {uri} as {device_id}...")
    async with websockets.connect(uri) as websocket:
        print("Connected to server!")
        
        # 1. Send Hello
        hello_msg = {
            "type": "device_hello",
            "device_id": device_id,
            "state": "OFF" # Default state
        }
        await websocket.send(json.dumps(hello_msg))
        print(f"Sent Hello: {hello_msg}")
        
        # Loop for messages
        try:
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "sync_state":
                    print(f"Received SYNC: State update to {data.get('state')}")
                    
                elif msg_type == "ping":
                    # Respond with Pong
                    # print("Received Ping, sending Pong...")
                    pong_msg = {"type": "pong"}
                    # Some servers might expect json, some text. 
                    # app/main.py checks if '"type": "pong"' in data.
                    # sending as json string works.
                    await websocket.send(json.dumps(pong_msg))
                    
                elif msg_type == "command":
                    action = data.get("action")
                    print(f"COMMAND RECEIVED: {action}")
                    
                    if action == "TURN_ON":
                        print(">>> LIGHT IS NOW ON <<<")
                        # Emulate state update confirming the action
                        update = {
                            "type": "state_update",
                            "device_id": device_id,
                            "state": "ON"
                        }
                        await websocket.send(json.dumps(update))
                        
                    elif action == "TURN_OFF":
                        print(">>> LIGHT IS NOW OFF <<<")
                        update = {
                            "type": "state_update",
                            "device_id": device_id,
                            "state": "OFF"
                        }
                        await websocket.send(json.dumps(update))
                        
                else:
                    print(f"Unknown message: {message}")
                    
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Dormitory Device Emulator")
    parser.add_argument("--device-id", type=str, default="mock_device_1", help="Device ID to emulate")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(device_client(args.device_id))
    except KeyboardInterrupt:
        print("\nExiting...")
