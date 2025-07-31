# --- Celery and WebSocket Configuration ---
RABBITMQ_URL = 'amqp://guest:guest@localhost:5672/'
WEBSOCKET_HOST = 'localhost'
WEBSOCKET_PORT = 8765

# --- API Keys (placeholder) ---
# In production, load these from environment variables or a secure vault.
API_KEYS = {
    'binance': {
        'apiKey': '22d58986ab817ec4b5df258849fba623fb37fe2d0f74bc643aee78b18b6e765a',
        'secret': '53345063fd96a009a2dfd71e4c3f114123661eda7948c5c3cc3b5ec347217a6e',
    },
    'bitmart': {
        'apiKey': 'YOUR_BITMART_API_KEY',
        'secret': 'YOUR_BITMART_SECRET_KEY',
        'uid': 'YOUR_BITMART_UID'
    }
}