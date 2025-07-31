
import ccxt
import time 

# api credentials



# Function to create for authenticated requests
class UnifiedExchangeAPI:
    """
    A unified interface to interact with multiple cryptocurrency exchanges using ccxt.
    """
    def __init__(self, exchange_name: str, api_key: str, secret_key: str, is_testnet: bool,**kwargs):
        """
        Initializes the exchange client.

        Args:
            exchange_name (str): The name of the exchange (e.g., 'binance', 'bitmart').
            api_key (str): The API key for the exchange.
            secret_key (str): The secret key for the exchange.
            **kwargs: Additional credentials like 'uid' for Bitmart.
        """
        if not hasattr(ccxt, exchange_name):
            raise ValueError(f"Exchange '{exchange_name}' is not supported by ccxt.")

        exchange_class = getattr(ccxt, exchange_name)
        
        # Prepare authentication credentials
        auth_params = {
            'apiKey': api_key,
            'secret': secret_key,
        }

        # Add sandbox URLs for Binance
        if exchange_name == 'binance' and is_testnet:
            auth_params['urls'] = {
                'api': {
                    'public': 'https://testnet.binance.vision/api',
                    'private': 'https://testnet.binance.vision/api',
                }
            }
        # Add any extra credentials required by specific exchanges (like Bitmart's UID)
        auth_params.update(kwargs)
        self.client = exchange_class(auth_params)
        # IMPORTANT: Set testnet mode AFTER initializing the client
        if is_testnet:
            self.client.set_sandbox_mode(True)
            print(f"Initialized client for {exchange_name} in TESTNET mode.")
        else:
            print(f"Initialized client for {exchange_name} in PRODUCTION mode.")

    # monitor ongoing orders
    def monitor_order(self, order_id: str, symbol: str):
        """
        Polls the exchange to check an order's status until it is closed or canceled.

        Returns:
            dict: The final order object from the exchange.
        """
        print(f"Monitoring order {order_id} for symbol {symbol}")

        # Set a timeout for the polling for 5 mins
        timeout = time.time()+ 300
    
        while time.time() < timeout:
            try:
                # Fetch the order status from the exchange
                order = self.client.fetch_order(order_id, symbol)
                status = order.get('status')

                print(f"Order {order_id} status is: {status}")

                # Check for a final state
                if status == 'closed' or status == 'filled' or status == 'canceled' or status == 'rejected':
                    print(f"Order {order_id} has reached a final state: {status}")
                    return order # Return the final order details
                
                # Wait for a few seconds before checking again to avoid rate limiting
                time.sleep(3)

            except Exception as e:
                print(f"Error fetching order {order_id}: {e}")
                # If the order is not found, it might be an issue, so we exit
                return {"status": "error", "message": str(e)}      
        
        print(f"Monitoring for order {order_id} timed out.")
        return {"status": "error", "message": "Monitoring timed out"}      


    def place_market_order(self, symbol: str, side: str, amount: float):
        """
        Places a market order.

        Args:
            symbol (str): The trading symbol (e.g., 'BTC/USDT').
            side (str): 'buy' or 'sell'.
            amount (float): The quantity of the asset to trade.

        Returns:
            dict: The order information from the exchange.
        """
        print(f"Placing MARKET {side} order for {amount} {symbol}... with credentials: API-KEY: {self.client.apiKey}, SECRET: {self.client.secret}")
        return self.client.create_market_order(symbol, side, amount)
    
    
    def place_limit_order(self, symbol: str, side: str, amount: float, price: float):
        """
        Places a limit order.

        Args:
            symbol (str): The trading symbol (e.g., 'BTC/USDT').
            side (str): 'buy' or 'sell'.
            amount (float): The quantity of the asset to trade.
            price (float): The price at which to place the order.

        Returns:
            dict: The order information from the exchange.
        """
        print(f"Placing LIMIT {side} order for {amount} {symbol} at {price}...")
        return self.client.create_limit_order(symbol, side, amount, price)
    
    def get_account_info(self):
        """
        Fetches the account balance information.
        Note: ccxt's fetchBalance is the unified method for this.
        """
        print("Fetching account balances...")
        # The 'private' scope is implied by providing API keys.
        return self.client.fetch_balance()