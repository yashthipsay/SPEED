
import ccxt

# api credentials



# Function to create for authenticated requests
class UnifiedExchangeAPI:
    """
    A unified interface to interact with multiple cryptocurrency exchanges using ccxt.
    """
    def __init__(self, exchange_name: str, api_key: str, secret_key: str, **kwargs):
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
        # Add any extra credentials required by specific exchanges (like Bitmart's UID)
        auth_params.update(kwargs)

        self.client = exchange_class(auth_params)
        print(f"Initialized client for {exchange_name}.")


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
        print(f"Placing MARKET {side} order for {amount} {symbol}...")
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