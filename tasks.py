# tasks.py
from celery_app import celery_app
from unified_exchange import UnifiedExchangeAPI  # Assuming the classes are in this file

@celery_app.task
def handle_api_request(request_data: dict):
    """
    A Celery task to handle a private API request for a user via the UnifiedExchangeAPI.
    """
    import server # We import server to use its broadcast function

    user_id = request_data.get('user_id')
    action = request_data.get('action')
    exchange_name = request_data.get('exchange')
    
    # --- Extract Credentials ---
    api_key = request_data.get('api_key')
    api_secret = request_data.get('api_secret')
    # Handle extra credentials like Bitmart's UID
    other_creds = {'uid': request_data.get('uid')} if request_data.get('uid') else {}

    print(f"Worker received job for User '{user_id}' | Exchange: '{exchange_name}' | Action: '{action}'")

    if not all([user_id, action, exchange_name, api_key, api_secret]):
        error_msg = {"status": "error", "message": "Missing required data (user_id, action, exchange, api_key, api_secret)"}
        server.broadcast_message(user_id, error_msg)
        return error_msg

    result = None
    try:
        # Initialize the unified client with user's specific keys
        client = UnifiedExchangeAPI(
            exchange_name=exchange_name,
            api_key=api_key,
            secret_key=api_secret,
            **other_creds
        )
        
        order_params = request_data.get('params', {})

        # Execute the requested action
        if action == 'get_account_info':
            result = client.get_account_info()
        elif action == 'place_market_order':
            result = client.place_market_order(**order_params)
        elif action == 'place_limit_order':
            result = client.place_limit_order(**order_params)
        else:
            result = {"status": "error", "message": f"Unknown action: {action}"}
            
    except Exception as e:
        print(f"An error occurred while processing request for {user_id}: {e}")
        # ccxt often raises specific, informative errors
        result = {"status": "error", "message": str(e)}

    # Send the result back to the specific user via the WebSocket server
    final_response = {"action": action, "status": "completed", "data": result}
    server.broadcast_message(user_id, final_response)
    
    return "Task completed."