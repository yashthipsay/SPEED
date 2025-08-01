
import ccxt
import time 
from symbol_mapper import SymbolMapper
# api credentials



# Function to create for authenticated requests
class UnifiedExchangeAPI:
    """
    A unified interface to interact with multiple cryptocurrency exchanges using ccxt.
    """
    def __init__(self, account_name: str, exchange_name: str, api_key: str, secret_key: str, symbol_mapper: SymbolMapper, is_testnet: bool, password: str = None, **kwargs):
        """
        Initializes the exchange client.

        Args:
            exchange_name (str): The name of the exchange (e.g., 'binance', 'bitmart').
            api_key (str): The API key for the exchange.
            secret_key (str): The secret key for the exchange.
            **kwargs: Additional credentials like 'uid' for Bitmart.
        """
        self.account_name = account_name
        self.exchange_name = exchange_name
        self.symbol_mapper = symbol_mapper
        if not hasattr(ccxt, exchange_name):
            raise ValueError(f"Exchange '{exchange_name}' is not supported by ccxt.")

        exchange_class = getattr(ccxt, exchange_name)
        
        # Prepare authentication credentials
        auth_params = {
            'apiKey': api_key,
            'secret': secret_key,
        }

        # Add password if provided (for exchanges like KuCoin, OKX)
        if password:
            auth_params['password'] = password

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
        if is_testnet and exchange_name not in ['bitmart']:
            self.client.set_sandbox_mode(True)
            print(f"Initialized client for {account_name} on {exchange_name} in TESTNET mode.")
        else:
            print(f"Initialized client for {account_name} on {exchange_name} in PRODUCTION mode.")

    # monitor ongoing orders
    def monitor_order(self, order_id: str, symbol: str):
        """
        Polls the exchange to check an order's status until it is closed or canceled.

        Returns:
            dict: The final order object from the exchange.
        """
        exchange_symbol = self._get_exchange_symbol(symbol)
        print(f"Monitoring order {order_id} for symbol {exchange_symbol}")

        # Set a timeout for the polling for 5 mins
        timeout = time.time()+ 300
    
        while time.time() < timeout:
            try:
                # Fetch the order status from the exchange
                order = self.client.fetch_order(order_id, exchange_symbol)
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

    def _get_exchange_symbol(self, universal_symbol: str) -> str:
        """Helper to translate a universal symbol to the exchange-specific format.""" 
        exchange_symbol = self.symbol_mapper.to_exchange_specific(universal_symbol, self.exchange_name)
        if not exchange_symbol:
            raise ValueError(f"Symbol '{universal_symbol}' is not available on exchange '{self.exchange_name}'")
        print(f"Translated universal symbol '{universal_symbol}' to exchange-specific '{exchange_symbol}' for {self.exchange_name}.")
        return exchange_symbol

    def monitor_position_pnl(self, filled_order: dict):
        """
        Monitors the unrealized Profit and Loss (PnL) of a position from a filled order.

        This function is a generator that yields PnL updates for a fixed duration.

        Args:
            filled_order (dict): The filled order object from ccxt.

        Yields:
            dict: A structured object containing the real-time PnL information.
        """
        if not filled_order or filled_order.get('status') not in ['closed', 'filled']:
            print("PnL monitoring required a filled order.")
            return
        
        # Extract initial details from the filled order
        pair_name = filled_order.get('symbol')
        entry_price = filled_order.get('average')
        quantity = filled_order.get('filled')
        position_side = filled_order.get('side')
        entry_timestamp = filled_order.get('timestamp')

        if not all([pair_name, entry_price, quantity, position_side]):
            print("Filled order object is missing required fields for PnL monitoring.")
            return

        # Ensure markets are loaded to get contract size for derivatives
        self.client.load_markets(pair_name)

        # Define market price by fetching market price for a pair
        market = self.client.market(pair_name)

        # 2. Get contractSize. Default to 1.0 for spot, use actual size for derivatives.
        if market.get('contract') and market.get('contractSize'):
            contract_size = market['contractSize']
        else:
            contract_size = 1.0
        
        print(f"✅ Starting PnL monitoring for position: {quantity} {pair_name}")

        try:
            # Monitor for 5 minutes, yielding PnL updates every second
            monitoring_end_time = time.time() + 300
            while time.time() < monitoring_end_time:
                # fetch the latest market price
                ticker = self.client.fetch_ticker(pair_name)
                current_price = ticker.get('last')

                if current_price is not None:
                    # 3. Calculate unrealized pnl, ACCOUNTING FOR CONTRACT SIZE
                    if position_side == 'buy':  # Long position
                        net_pnl = (current_price - entry_price) * quantity * contract_size
                    else:  # Short position
                        net_pnl = (entry_price - current_price) * quantity * contract_size

                    # Construct the structured PnL object
                    pnl_update = {
                        "connector_name": self.account_name,
                        "pair_name": pair_name,
                        "entry_timestamp": entry_timestamp,
                        "entry_price": entry_price,
                        "quantity": quantity,
                        "position_side": "long" if position_side == 'buy' else "short",
                        "current_price": current_price,
                        "NetPnL": net_pnl
                    }
                    yield pnl_update
                
                time.sleep(5)  # Pause between updates to avoid rate-limiting

        except Exception as e:
            print(f"Error during PnL monitoring for {pair_name}: {e}")
        finally:
            print(f"⏹️ Finished PnL monitoring for position: {pair_name}")

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
        exchange_symbol = self._get_exchange_symbol(symbol)
        print(f"Placing MARKET {side} order for {amount} {exchange_symbol}... with credentials: API-KEY: {self.client.apiKey}, SECRET: {self.client.secret}")
        return self.client.create_market_order(exchange_symbol, side, amount)


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
        exchange_symbol = self._get_exchange_symbol(symbol)
        print(f"Placing LIMIT {side} order for {amount} {exchange_symbol} at {price}...")
        return self.client.create_limit_order(exchange_symbol, side, amount, price)

    def get_account_info(self):
        """
        Fetches the account balance information.
        Note: ccxt's fetchBalance is the unified method for this.
        """
        print("Fetching account balances...")
        # The 'private' scope is implied by providing API keys.
        return self.client.fetch_balance()