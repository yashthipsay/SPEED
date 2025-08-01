import ccxt
import json
import os
import re
import time

class SymbolMapper:
    """
    A comprehensive utility to map trading symbols between a universal format
    (e.g., 'BTC/USDT') and exchange-specific formats (e.g., 'BTC-USDT', 'BTCUSDT').

    It works by fetching all available markets from the specified exchanges
    and creating a fast, two-way lookup table.
    """

    def __init__(self, cache_filename="exchange_markets.json", cache_ttl_seconds=86400):
        """
        Initializes the mapper.

        Args:
            cache_filename (str): The file to store market data to avoid re-fetching.
            cache_ttl_seconds (int): Time-to-live for the cache file in seconds (default: 24 hours).
        """
        self.cache_filename = cache_filename
        self.cache_ttl = cache_ttl_seconds
        self.markets = self._load_or_fetch_markets()

    def _is_cache_valid(self) -> bool:
        """Checks if the cache file exists and is not expired."""
        if not os.path.exists(self.cache_filename):
            return False
        
        cache_age = time.time() - os.path.getmtime(self.cache_filename)
        return cache_age < self.cache_ttl
    
    def _load_or_fetch_markets(self) -> dict:
        """Loads market data from cache or fetches it from exchanges if the cache is invalid."""
        if self._is_cache_valid():
            print("✅ Loading market data from valid cache...")
            with open(self.cache_filename, 'r') as f:
                return json.load(f)
        
        print("⚠️ Cache is invalid or missing. Fetching live market data from exchanges...")
        return self.fetch_all_markets()
    
    def fetch_all_markets(self) -> dict:
        """
        Connects to specified exchanges to fetch and structure all market data.
        """
        # Add any exchanges you need to support here
        exchanges_to_fetch = ['binance', 'binanceusdm', 'okx', 'kucoin', 'bitmart', 'deribit']
        all_markets = {}

        for exchange_id in exchanges_to_fetch:
            try:
                print(f"Fetching markets for {exchange_id}...")
                exchange = getattr(ccxt, exchange_id)()
                exchange_markets = exchange.load_markets()
                
                # Structure the data for easy lookup
                all_markets[exchange_id] = {
                    market['symbol']: market['id'] for market in exchange_markets.values()
                }
            except Exception as e:
                print(f"Could not fetch markets for {exchange_id}: {e}")

        # Save the freshly fetched data to the cache file
        with open(self.cache_filename, 'w') as f:
            json.dump(all_markets, f, indent=4)
        
        print("✅ Successfully fetched and cached all market data.")
        return all_markets
    
    def to_exchange_specific(self, universal_symbol: str, exchange_id: str) -> str | None:
        """
        Converts a universal symbol (e.g., 'BTC/USDT') to the format required
        by a specific exchange.

        Args:
            universal_symbol (str): The standardized symbol.
            exchange_id (str): The ID of the target exchange (e.g., 'binance').

        Returns:
            str | None: The exchange-specific symbol ID or None if not found.
        """
        if exchange_id not in self.markets:
            print(f"Error: Exchange '{exchange_id}' not found in market data.")
            return None
            
        return self.markets[exchange_id].get(universal_symbol)
    
    def to_universal(self, exchange_symbol_id: str, exchange_id: str) -> str | None:
        """
        Converts an exchange-specific symbol ID back to the universal format.

        Args:
            exchange_symbol_id (str): The symbol ID from the exchange.
            exchange_id (str): The ID of the exchange.

        Returns:
            str | None: The universal symbol or None if not found.
        """
        if exchange_id not in self.markets:
            return None
        
        # This creates a reverse mapping on-the-fly to find the universal symbol
        reverse_map = {v: k for k, v in self.markets[exchange_id].items()}
        return reverse_map.get(exchange_symbol_id)
    
# --- Standalone script to generate the cache ---
if __name__ == '__main__':
    print("Running SymbolMapper in standalone mode to generate the market data cache.")
    mapper = SymbolMapper()
    print("\n--- Cache Generation Complete ---")
    print(f"Market data has been saved to '{mapper.cache_filename}'.")
    print("\n--- Example Usage ---")
    
    # Test converting a universal symbol TO an exchange-specific one
    universal = 'BTCUSDT'
    exchange = 'binance'
    specific_id = mapper.to_exchange_specific(universal, exchange)
    print(f"Universal '{universal}' on '{exchange}' is Exchange-Specific ID: '{specific_id}'")

    # Test converting an exchange-specific symbol BACK to universal
    if specific_id:
        universal_check = mapper.to_universal(specific_id, exchange)
        print(f"Exchange-Specific ID '{specific_id}' on '{exchange}' is Universal: '{universal_check}''")