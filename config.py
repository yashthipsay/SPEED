# --- Celery and WebSocket Configuration ---
RABBITMQ_URL = 'amqp://guest:guest@localhost:5672//'
WEBSOCKET_HOST = 'localhost'
WEBSOCKET_PORT = 8765

# --- API Keys (placeholder) ---
# In production, load these from environment variables or a secure vault.
API_KEYS = {
    'binance': {
        'apiKey': 'YOUR_BINANCE_API_KEY',
        'secret': 'YOUR_BINANCE_SECRET_KEY',
    },
    'bitmart': {
        'apiKey': 'YOUR_BITMART_API_KEY',
        'secret': 'YOUR_BITMART_SECRET_KEY',
        'uid': 'YOUR_BITMART_UID'
    }
}