import asyncio
import json
import config
import websockets
from fastapi import FastAPI, WebSocket
from tasks import handle_api_request
from aio_pika import connect_robust, ExchangeType, IncomingMessage

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
            websocket = CONNECTED_CLIENTS.get(user_id)
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
        websocket = CONNECTED_CLIENTS.get(user_id)
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
    user_id = None
    try:
        # The first message should be for authentication to identify the user
        auth_message = await websocket.receive_text()
        data = json.loads(auth_message)
        user_id = data.get('user_id')
        
        if not user_id:
            await websocket.close(1008, "User ID is required for connection.")
            return

        CONNECTED_CLIENTS[user_id] = websocket
        print(f"User '{user_id}' connected.")
        await websocket.send_json({"status": "connected", "user_id": user_id})

        # proxy further messages into Celery
        while True:
            msg = await websocket.receive_text()
            req = json.loads(msg)
            action = req.get("action")

            if action in ("get_account_info", "place_market_order", "place_limit_order"):
                # proxy trading actions into Celery
                req["user_id"] = user_id
                handle_api_request.delay(req)
                await websocket.send_json({"status": "processing", "action": action})

            elif action in ("start_orderbook", "stop_orderbook"):
                # echo orderbook commands straight back to client
                # so trading_client.handle_server_messages() can start/stop polling
                await websocket.send_json({
                    "action": action,
                    "exchange": req.get("exchange"),
                    "symbol": req.get("symbol", "BTC/USDT")
                })

            else:
                await websocket.send_json({
                    "status": "error",
                    "message": f"Unknown action: {action}"
                })

    except websockets.exceptions.ConnectionClosed:
        print(f"User '{user_id}' disconnected.")
    finally:
        # Clean up the connection on disconnect
        if user_id and user_id in CONNECTED_CLIENTS:
            del CONNECTED_CLIENTS[user_id]

@app.websocket("/")
async def websocket_endpoint(ws: WebSocket):
    await ws_handler(ws)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=config.WEBSOCKET_HOST, port=config.WEBSOCKET_PORT, reload=True)