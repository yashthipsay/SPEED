# server.py
import asyncio
import websockets
import json
from tasks import handle_api_request # Import our Celery task
import config

# This dictionary maps a user_id to their WebSocket connection object.
# In a production system, this mapping should be stored in a shared cache like Redis.
CONNECTED_CLIENTS = {}

def broadcast_message(user_id: str, message: dict):
    """
    Finds a user's WebSocket connection and sends them a message.
    This function is called by the Celery worker.
    """
    # This needs to run in the main server's event loop
    async def send_async():
        websocket = CONNECTED_CLIENTS.get(user_id)
        if websocket:
            try:
                await websocket.send(json.dumps(message))
                print(f"Sent update to user {user_id}")
            except websockets.exceptions.ConnectionClosed:
                # Clean up if the user disconnected
                del CONNECTED_CLIENTS[user_id]
        else:
            print(f"Could not send update, user {user_id} not connected.")

    # Get the running event loop from the main server thread and run the task
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(send_async())

async def handler(websocket, path):
    """Handles incoming WebSocket connections and messages."""
    user_id = None
    try:
        # The first message should be for authentication to identify the user
        auth_message = await websocket.recv()
        data = json.loads(auth_message)
        user_id = data.get('user_id')
        
        if not user_id:
            await websocket.close(1008, "User ID is required for connection.")
            return

        CONNECTED_CLIENTS[user_id] = websocket
        print(f"User '{user_id}' connected.")
        await websocket.send(json.dumps({"status": "connected", "user_id": user_id}))

        # Listen for subsequent requests from this user
        async for message in websocket:
            request_data = json.loads(message)
            # Add user_id to the request payload for the worker
            request_data['user_id'] = user_id
            
            # Send the job to the Celery worker queue
            handle_api_request.delay(request_data)
            
            # Immediately acknowledge receipt of the request
            await websocket.send(json.dumps({"status": "processing", "action": request_data.get('action')}))

    except websockets.exceptions.ConnectionClosed:
        print(f"User '{user_id}' disconnected.")
    finally:
        # Clean up the connection on disconnect
        if user_id and user_id in CONNECTED_CLIENTS:
            del CONNECTED_CLIENTS[user_id]

async def main():
    print(f"WebSocket server starting on ws://{config.WEBSOCKET_HOST}:{config.WEBSOCKET_PORT}")
    async with websockets.serve(handler, config.WEBSOCKET_HOST, config.WEBSOCKET_PORT):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())