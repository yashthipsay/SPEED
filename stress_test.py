import asyncio
import websockets
import json
import random
import time
import config

TOTAL_CLIENTS = 200

SERVER_URI = f"ws://{config.WEBSOCKET_HOST}:{config.WEBSOCKET_PORT}"

TEST_ACCOUNTS = [
    {
        "account_name": "binance_coinm_test",
        "exchange": "binancecoinm",
        "api_key": "22d58986ab817ec4b5df258849fba623fb37fe2d0f74bc643aee78b18b6e765a",
        "api_secret": "53345063fd96a009a2dfd71e4c3f114123661eda7948c5c3cc3b5ec347217a6e",
        "is_testnet": True,
        "symbols": ["BTC/USDT", "ETH/USDT"]
    },
    {
        "account_name": "binance_usdm_test",
        "exchange": "binanceusdm",
        "api_key": "22d58986ab817ec4b5df258849fba623fb37fe2d0f74bc643aee78b18b6e765a",
        "api_secret": "53345063fd96a009a2dfd71e4c3f114123661eda7948c5c3cc3b5ec347217a6e",
        "is_testnet": True,
        "symbols": ["BTC/USDT:USDT", "ETH/USDT:USDT"]

    },
    # {
    #     "account_name": "deribit_test",
    #     "exchange": "deribit",
    #     "api_key": "oROD-D2E",
    #     "api_secret": "hxMWiy9BYaAjP5sfOhNuoOco1GdgS1yteVakioCRI_8",
    #     "is_testnet": True,
    #     "symbols": ["BTC/USDC"]

    # },
    # {
    #     "account_name": "okx_test",
    #     "exchange": "okx",
    #     "api_key": "475a3dde-6b33-4fbc-a7a6-454202a4804d",
    #     "api_secret": "E00052E9F18323B53472CD64AF194764",
    #     "password": "7NGWN%%DEzn9@(8",
    #     "is_testnet": True,
    #     "symbols": ["BTC/USDT", "ETH/USDT"]
    # }
]

async def run_single_client(client_id):
    """
    Simulates a single user connecting, sending one order, and disconnecting.
    """
    try:
        async with websockets.connect(SERVER_URI) as websocket:
            # Authenticate
            user_id = f"ws_stress_user_{client_id}"
            await websocket.send(json.dumps({"user_id": user_id}))
            auth_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
            auth_data = json.loads(auth_msg)
            if auth_data.get("status") != "connected":
                print(f"Client {client_id}: auth failed -> {auth_data}")
                return ("failed", None)

            # 2. Start timer only after auth succeeded
            start_ts = time.monotonic()
            
            # Prepare a random order
            account_config = random.choice(TEST_ACCOUNTS)
            order_type = "place_market_order"

            params = {
                "symbol": random.choice(account_config["symbols"]),
                "side": random.choice(["buy", "sell"]),
                "amount": round(random.uniform(0.001, 0.01), 5)
            }

            # if order_type == "place_limit_order":
            #     # For limit orders, let's just add a placeholder price
            #     # A real scenario would fetch the current price first.
            #     params["price"] = round(random.uniform(20000, 60000), 2)

            order_payload = {
                "user_id": user_id,
                "account_name": account_config["account_name"],
                "exchange": account_config["exchange"],
                "api_key": account_config["api_key"],
                "api_secret": account_config["api_secret"],
                # "password": account_config["password"],
                "is_testnet": account_config["is_testnet"],
                "action": order_type,
                "params": params
            }

            if account_config.get("exchange") == "okx":
                order_payload["password"] = account_config["password"]

            # 3. Send the order
            await websocket.send(json.dumps(order_payload))
            
            # 4. Wait for final execution message
            exec_time = None
            while True:
                msg = await asyncio.wait_for(websocket.recv(), timeout=30)
                data = json.loads(msg)
                # look for our order action + terminal status
                if data.get("action") == order_type and data.get("status") in ("filled", "closed", "error"):
                    exec_time = time.monotonic() - start_ts
                    break

            return ("success", exec_time)
        
    except Exception as e:
        print(f"Client {client_id}: failed with {e}")
        return ("failed", None)
    
async def main():
    """Launches all concurrent clients and summarizes the results."""
    print(f"🚀 Starting WebSocket stress test with {TOTAL_CLIENTS} concurrent clients...")

    # Create a list of tasks, one for each client
    tasks = [run_single_client(i) for i in range(TOTAL_CLIENTS)]

    results = await asyncio.gather(*tasks)

    end_time = time.time()

    # summarize
    success_times = [t for status, t in results if status == "success" and t is not None]
    success_count = len(success_times)
    failed_count  = TOTAL_CLIENTS - success_count
    avg_time      = sum(success_times) / success_count if success_count else 0
    
    print("\n--- Summary ---")
    print(f"Total clients:     {TOTAL_CLIENTS}")
    print(f"Successful orders: {success_count}")
    print(f"Failed orders:     {failed_count}")
    print(f"Avg exec time:     {avg_time:.3f} sec")

if __name__ == "__main__":
    # Ensure you have all services (server, celery, rabbitmq) running
    asyncio.run(main())