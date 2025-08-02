import asyncio
import json
import src.config as config
import websockets
from fastapi import FastAPI, WebSocket
from src.tasks.tasks import handle_api_request, task_persist_orderbook_data
from src.celery_app import celery_app
from aio_pika import connect_robust, ExchangeType, IncomingMessage
from starlette.websockets import WebSocketDisconnect

app = FastAPI()

# This dictionary maps a user_id to their WebSocket connection object.
# In a production system, this mapping should be stored in a shared cache like Redis.
CONNECTED_CLIENTS = {}

@app.on_event("startup")
async def startup_rabbitmq_listener():
    # connect to RabbitMQ and bind to our fanout exchange
    connection = await connect_robust(config.RABBITMQ_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange("notifications_exchange", ExchangeType.FANOUT)
    queue = await channel.declare_queue(exclusive=True)
    await queue.bind(exchange)

    async def on_message(message: IncomingMessage):
        async with message.process():
            body = json.loads(message.body)
            user_id = body.get("user_id")
            payload = body.get("payload")
            entry = CONNECTED_CLIENTS.get(user_id, {})
            websocket = entry.get("websocket")
            if websocket:
                await websocket.send_json(payload)
                print(f"Broadcasted via WS to {user_id}: {payload}")

    await queue.consume(on_message)


def broadcast_message(user_id: str, message: dict):
    """
    Finds a user's WebSocket connection and sends them a message.
    This function is called by the Celery worker.
    """
    # This needs to run in the main server's event loop
    async def send_async():
        entry = CONNECTED_CLIENTS.get(user_id, {})
        websocket = entry.get("websocket")
        if websocket:
            try:
                await websocket.send_json(message)
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

async def ws_handler(websocket: WebSocket):
    """Handles incoming WebSocket connections and messages."""
    await websocket.accept()
    account_name = None
    user_id = None
    try:
        # The first message should be for authentication to identify the user
        auth_message = await websocket.receive_text()
        data = json.loads(auth_message)
        user_id = data.get('user_id')
        account_name = data.get('account_name')
        
        if not user_id:
            await websocket.close(1008, "User ID is required for connection.")
            return

        CONNECTED_CLIENTS[user_id] = {"websocket": websocket, "persistence_task_id": None}
        print(f"User '{account_name}' with user ID '{user_id}' connected.")
        await websocket.send_json({"status": "connected", "account_name": account_name,"user_id": user_id})

        # proxy further messages into Celery
        while True:
            msg = await websocket.receive_text()
            req = json.loads(msg)
            action = req.get("action")

            if action in ("get_account_info", "place_market_order", "place_limit_order", "analyze_and_place_order"):
                # proxy trading actions into Celery
                req["user_id"] = user_id
                handle_api_request.delay(req)
                await websocket.send_json({"status": "processing", "action": action})

            elif action == "start_orderbook":
                # This action now serves two purposes:
                # 1. Echo back to the client to start the UI polling.
                # 2. Start the backend data persistence task.
                exchange = req.get("exchange")
                symbol = req.get("symbol", "BTC/USDT")
                task = task_persist_orderbook_data.delay(
                    exchange, symbol, config.DATA_CAPTURE_INTERVAL_SECONDS
                )
                # Now this works because CONNECTED_CLIENTS[user_id] is a dict
                CONNECTED_CLIENTS[user_id]["persistence_task_id"] = task.id
                print(f"Launched persistence task {task.id} for user {user_id}")

                # Echo back on the socket stored in the dict:
                await CONNECTED_CLIENTS[user_id]["websocket"].send_json({
                    "action": action, "exchange": exchange, "symbol": symbol
                })
            elif action == "stop_orderbook_persistence":
                task_id = CONNECTED_CLIENTS[user_id].get("persistence_task_id")
                if task_id:
                    print(f"Revoking persistence task {task_id} for user {user_id}")
                    celery_app.control.revoke(task_id, terminate=True)
                    CONNECTED_CLIENTS[user_id]["persistence_task_id"] = None
                    await websocket.send_json({"status": "stopped", "action": action})
                else:
                    await websocket.send_json({"status": "error", "message": "No active persistence task found."})
            
            elif action == "stop_orderbook":
                # This remains for stopping the UI polling on the client
                await websocket.send_json({"action": action})

            else:
                await websocket.send_json({
                    "status": "error",
                    "message": f"Unknown action: {action}"
                })

    except WebSocketDisconnect:
        print(f"User '{user_id}' disconnected (normal closure).")
    finally:
        # Clean up the connection on disconnect
        if user_id and user_id in CONNECTED_CLIENTS:
            # Also terminate any running persistence task on disconnect
            task_id = CONNECTED_CLIENTS[user_id].get("persistence_task_id")
            if task_id:
                print(f"Client disconnected, revoking task {task_id}")
                celery_app.control.revoke(task_id, terminate=True)
            del CONNECTED_CLIENTS[user_id]

@app.websocket("/")
async def websocket_endpoint(ws: WebSocket):
    await ws_handler(ws)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=config.WEBSOCKET_HOST, port=config.WEBSOCKET_PORT, reload=True)