import os
import sys
import pika
import json
import config
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
def handle_api_request(request_data: dict):
    import server  # now resolves correctly

    """
    A Celery task to handle a private API request for a user via the UnifiedExchangeAPI.
    """
    user_id = request_data.get('user_id')
    action = request_data.get('action')
    exchange_name = request_data.get('exchange')
    
    # --- Extract Credentials ---
    api_key = request_data.get('api_key')
    api_secret = request_data.get('api_secret')
    is_testnet = request_data.get('is_testnet', False)
    other_creds = {'uid': request_data.get('uid')} if request_data.get('uid') else {}

    print(f"Worker received job for User '{user_id}' | Exchange: '{exchange_name}' | Action: '{action}'")

    if not all([user_id, action, exchange_name, api_key, api_secret]):
        error_msg = {"status": "error", "message": "Missing required data (user_id, action, exchange, api_key, api_secret)"}
        server.broadcast_message(user_id, error_msg)
        return error_msg

    try:
        client = UnifiedExchangeAPI(
            exchange_name=exchange_name,
            api_key=api_key,
            secret_key=api_secret,
            is_testnet=is_testnet,
            **other_creds
        )
        order_params = request_data.get('params', {})

        if action == 'get_account_info':
            result = client.get_account_info()
        elif action == 'place_market_order':
            result = client.place_market_order(**order_params)
        elif action == 'place_limit_order':
            initial = client.place_limit_order(**order_params)

            # publish initial "placed" state
            publish_result({
                "user_id": user_id,
                "payload": {"action": action, "status": "placed", "data": initial}
            })

            # now poll until it's closed/filled
            result = client.monitor_order(initial['id'], order_params['symbol'])
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