import os
import sys
import pika
import json
import config
from symbol_mapper import SymbolMapper 
# ensure the project root is on PYTHONPATH so we can import server
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from celery_app import celery_app
from unified_exchange import UnifiedExchangeAPI

def publish_result(body: dict):
    """
    Publishes the result to a RabbitMQ fanout exchange.
    """
    connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
    channel = connection.channel()
    channel.exchange_declare(exchange='notifications_exchange', exchange_type='fanout')
    channel.basic_publish(
        exchange='notifications_exchange',
        routing_key='',
        body=json.dumps(body)
    )
    connection.close()
    print(f"Worker published FINAL result for user {body}")


@celery_app.task
def task_monitor_pnl(request_data: dict, filled_order: dict):
    """
    A dedicated Celery task to monitor PnL for a filled order asynchronously.
    """
    user_id = request_data.get('user_id')
    print(f"🚀 Starting background PnL monitoring for user {user_id}...")

    # We must re-initialize the client within the new task's process
    client = UnifiedExchangeAPI(
        account_name=request_data.get('account_name'),
        exchange_name=request_data.get('exchange'),
        api_key=request_data.get('api_key'),
        secret_key=request_data.get('api_secret'),
        password=request_data.get('password'), # Pass the password
        symbol_mapper=SymbolMapper(),
        is_testnet=request_data.get('is_testnet', False)
    )

    # The PnL monitoring loop now runs here, in the background
    for pnl_update in client.monitor_position_pnl(filled_order):
        publish_result({
            "user_id": user_id,
            "payload": {"action": "pnl_update", "status": "monitoring", "data": pnl_update}
        })
    
    # Notify client that monitoring has stopped
    publish_result({"user_id": user_id, "payload": {"action": "pnl_update", "status": "stopped"}})
    return "Background PnL monitoring complete."

@celery_app.task
def handle_api_request(request_data: dict):
    import server  # now resolves correctly

    """
    A Celery task to handle a private API request for a user via the UnifiedExchangeAPI.
    """
    account_name = request_data.get('account_name')
    user_id = request_data.get('user_id')
    action = request_data.get('action')
    exchange_name = request_data.get('exchange')
    
    # --- Extract Credentials ---
    api_key = request_data.get('api_key')
    api_secret = request_data.get('api_secret')
    password = request_data.get('password') # Extract password
    is_testnet = request_data.get('is_testnet', False)
    other_creds = {'uid': request_data.get('uid')} if request_data.get('uid') else {}

    print(f"Worker received job for User '{user_id}' | Exchange: '{exchange_name}' | Action: '{action}'")

    if not all([account_name, user_id, action, exchange_name, api_key, api_secret]):
        error_msg = {"status": "error", "message": "Missing required data (user_id, action, exchange, api_key, api_secret)"}
        server.broadcast_message(user_id, error_msg)
        return error_msg

    try:
        client = UnifiedExchangeAPI(
            account_name=account_name,
            exchange_name=exchange_name,
            api_key=api_key,
            secret_key=api_secret,
            password=password, # Pass the password
            symbol_mapper=SymbolMapper(),
            is_testnet=is_testnet,
            **other_creds
        )
        order_params = request_data.get('params', {})

        if action == 'get_account_info':
            result = client.get_account_info()
        elif action == 'place_market_order':
            initial = client.place_market_order(**order_params)
            publish_result({
                "user_id": user_id,
                "payload": {"action": action, "status": "placed", "data": initial}
            })
            
            filled_order = client.monitor_order(initial['id'], order_params['symbol'])

            publish_result({
                "user_id": user_id,
                "payload": {"action": action, "status": "filled", "data": filled_order}
            })

            if filled_order.get('status') in ['closed', 'filled']:
                # Start PnL monitoring if the order was filled
                task_monitor_pnl.delay(request_data, filled_order)

            # set result
            result = filled_order
        elif action == 'place_limit_order':
            initial = client.place_limit_order(**order_params)

            # publish initial "placed" state
            publish_result({
                "user_id": user_id,
                "payload": {"action": action, "status": "placed", "data": initial}
            })

            # now poll until it's closed/filled
            filled_order = client.monitor_order(initial['id'], order_params['symbol'])

            # Publish final order status
            publish_result({
                "user_id": user_id,
                "payload": {"action": action, "status": filled_order.get("status"), "data": filled_order}
            })

            # If filled, start PnL monitoring
            if filled_order.get('status') in ['closed', 'filled']:
                task_monitor_pnl.delay(request_data, filled_order)
            return "Limit order task and potential PnL monitoring complete."
        else:
            result = {"status": "error", "message": f"Unknown action: {action}"}
            
    except Exception as e:
        print(f"An error occurred while processing request for {user_id}: {e}")
        result = {"status": "error", "message": str(e)}

    # final notification when order is closed/rejected/canceled
    final_payload = {
        "action": action,
        "status": result.get("status"),
        "data": result
    }

    # also publish to RabbitMQ
    publish_result({
        "user_id": user_id,
        "payload": final_payload
    })
    return "Task and monitoring completed."