import asyncio
import websockets
import sys

URI = "ws://localhost:8000/ws"

async def run_mock_device():
    print(f"Connecting to {URI}...")
    try:
        async with websockets.connect(URI) as websocket:
            print("Connected to server!")
            
            # Initial state
            current_state = "OFF"
            await websocket.send(f"STATE:{current_state}")
            print(f"Sent initial state: STATE:{current_state}")

            while True:
                try:
                    message = await websocket.recv()
                    print(f"\n[Received Command]: {message}")

                    if message == "ON":
                        print("Turning Light ON...")
                        current_state = "ON"
                        # Simulate processing time
                        await asyncio.sleep(0.5) 
                        await websocket.send(f"STATE:{current_state}")
                        print(f"Sent confirmation: STATE:{current_state}")
                    
                    elif message == "OFF":
                        print("Turning Light OFF...")
                        current_state = "OFF"
                        # Simulate processing time
                        await asyncio.sleep(0.5)
                        await websocket.send(f"STATE:{current_state}")
                        print(f"Sent confirmation: STATE:{current_state}")
                    
                    else:
                        print(f"Unknown command: {message}")

                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed by server.")
                    break
    except Exception as e:
        print(f"Failed to connect or connection error: {e}")
        print("Ensure the server is running (uvicorn main:app --reload)")

if __name__ == "__main__":
    # Check checks for windows loop policy if needed (usually handled by asyncio in newer python, but explicit is safe)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(run_mock_device())
    except KeyboardInterrupt:
        print("\nMock device stopped.")
