import asyncio
import websockets
import json
import argparse
import config
import ccxt.async_support as ccxt
from collections import deque
import sys, time

# --- Global state for the Terminal UI ---
best_bid_ask_display = "Waiting for orderbook command..."
l2_book_display = "Connect and send 'start_orderbook' action to begin."
message_log = deque(maxlen=10)
orderbook_task = None
current_exchange = None
current_symbol = None

def format_best_bid_ask(order_book: dict) -> str:
    """Formats just the best bid and ask summary."""
    if not order_book or not order_book.get('bids') or not order_book.get('asks'):
        return "Best Bid/Ask data unavailable."
    
    best_bid = order_book['bids'][0][0]
    best_ask = order_book['asks'][0][0]
    spread = best_ask - best_bid
    
    return f"Best Bid: {best_bid:,.2f} | Best Ask: {best_ask:,.2f} | Spread: {spread:,.2f}"

def format_l2_table(order_book: dict, limit: int = 10) -> str:
    """Formats the top levels of the L2 order book into a table."""
    if not order_book or not order_book.get('bids') or not order_book.get('asks'):
        return "L2 table data unavailable."

    asks = sorted(order_book['asks'])[:limit]
    bids = sorted(order_book['bids'], reverse=True)[:limit]
    
    header = f"{'Qty':>12} @ {'Price':<14} | {'Price':>14} @ {'Qty':<12}\n"
    header += "-" * 56
    
    rows = [header]
    for i in range(limit):
        bid_price, bid_qty = (bids[i][0], bids[i][1]) if i < len(bids) else ('-', '-')
        ask_price, ask_qty = (asks[i][0], asks[i][1]) if i < len(asks) else ('-', '-')
        rows.append(f"{bid_qty:>12.4f} @ {bid_price:<14.2f} | {ask_price:>14.2f} @ {ask_qty:<12.4f}")
        
    return "\n".join(rows)

async def send_user_commands(ws):
    """
    Reads lines from stdin (one JSON command per line) and
    pushes them to the server over the WebSocket.
    """
    loop = asyncio.get_event_loop()
    while True:
        # run input() in a thread so we don’t block the event loop
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            continue
        line = line.strip()
        try:
            req = json.loads(line)
            await ws.send(json.dumps(req))
            message_log.append(f"[{time.strftime('%H:%M:%S')}] >> {req}")
        except json.JSONDecodeError:
            message_log.append(f"[{time.strftime('%H:%M:%S')}] >> Invalid JSON: {line}")

async def poll_order_book(exchange_id, symbol):
    """Coroutine to fetch order book data and update the display variables."""
    global best_bid_ask_display, l2_book_display
    client = getattr(ccxt, exchange_id)()
    try:
        while True:
            try:
                snapshot = await client.fetch_order_book(symbol)
                best_bid_ask_display = format_best_bid_ask(snapshot)
                l2_book_display = format_l2_table(snapshot)
            except Exception as e:
                error_message = f"Error fetching order book: {e}"
                best_bid_ask_display = error_message
                l2_book_display = ""
            await asyncio.sleep(1)
    finally:
        await client.close()

async def handle_server_messages(websocket):
    """Coroutine to listen for messages from our trading server."""
    import time
    global message_log, orderbook_task, current_exchange, current_symbol, best_bid_ask_display, l2_book_display
    
    async for message in websocket:
        timestamp = time.strftime('%H:%M:%S', time.localtime())
        log_entry = f"[{timestamp}] << {message}"
        message_log.append(log_entry)
        
        try:
            data = json.loads(message)
            action = data.get('action')
            
            if action == 'start_orderbook':
                exchange = data.get('exchange')
                symbol = data.get('symbol', 'BTC/USDT')
                
                if exchange:
                    # Stop existing orderbook task if running
                    if orderbook_task and not orderbook_task.done():
                        orderbook_task.cancel()
                    
                    current_exchange = exchange
                    current_symbol = symbol
                    best_bid_ask_display = f"Starting orderbook for {symbol} on {exchange}..."
                    l2_book_display = "Loading..."
                    
                    # Start new orderbook polling
                    orderbook_task = asyncio.create_task(poll_order_book(exchange, symbol))
                    message_log.append(f"[{timestamp}] Started orderbook: {exchange} {symbol}")
                    
            elif action == 'stop_orderbook':
                if orderbook_task and not orderbook_task.done():
                    orderbook_task.cancel()
                best_bid_ask_display = "Orderbook stopped."
                l2_book_display = "Send 'start_orderbook' to resume."
                message_log.append(f"[{timestamp}] Stopped orderbook")
                
        except json.JSONDecodeError:
            pass  # Message wasn't JSON, just log it

async def display_ui():
    """Coroutine to continuously redraw the terminal UI."""
    while True:
        print("\033c", end="")  # Clears the console
        print("--- Trading Client (Orderbook Mode) ---")
        if current_exchange and current_symbol:
            print(f"Exchange: {current_exchange} | Symbol: {current_symbol}")
        print(best_bid_ask_display)
        print("\n--- L2 Order Book ---")
        print(l2_book_display)
        print("\n--- Server Message Log ---")
        for msg in message_log:
            print(msg)
        print("\n--- Commands ---")
        print("Send via WebSocket: {'action': 'start_orderbook', 'exchange': 'binance', 'symbol': 'BTC/USDT'}")
        print("Send via WebSocket: {'action': 'stop_orderbook'}")
        await asyncio.sleep(0.1)  # UI Redraw rate

async def run_client(user_id):
    """Sets up all tasks and connects to the server."""
    global message_log
    uri = f"ws://{config.WEBSOCKET_HOST}:{config.WEBSOCKET_PORT}"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"user_id": user_id}))
            response = await websocket.recv()
            message_log.append(f"Server response: {response}")

            # launch listen/display/send coroutines
            listener = asyncio.create_task(handle_server_messages(websocket))
            ui       = asyncio.create_task(display_ui())
            sender   = asyncio.create_task(send_user_commands(websocket))

            await asyncio.gather(listener, ui, sender)

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading client waiting for orderbook commands.")
    parser.add_argument("user_id", help="A unique ID for the user (e.g., trader_alpha).")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_client(args.user_id))
    except KeyboardInterrupt:
        print("\nClient stopped.")