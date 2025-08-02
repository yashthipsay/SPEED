# WebSocket API Instructions

**Endpoint:** ws://localhost:8765/ws

## 1. Authenticate
Send (JSON):
```json
{
  "user_id": "trader_alpha",
  "account_name": "yash"
}
```

Response:
```json
{"status":"connected","user_id":"trader_alpha","account_name":"yash"}
```


## 2. Place Market order

Send:
```json
{
  "account_name": "yash",
  "user_id": "trader_alpha",
  "action": "place_market_order",
  "exchange": "binanceusdm",
  "is_testnet": true,
  "api_key": "YOUR_BINANCE_API_KEY",
  "api_secret": "YOUR_BINANCE_SECRET_KEY",
  "params": {
    "symbol": "BTC/USDT:USDT",
    "side": "buy",
    "amount": 0.001,
    "price": 113757
  }
}
```

Acknowledge:
```json
{"status":"processing","action":"place_market_order"}
```

Result:
```json
{"action":"place_market_order","status":"filled","data":{…}}
```

## 3. Place Limit order

Send:
```json
{
  "account_name": "yash",
  "user_id": "trader_alpha",
  "action": "place_limit_order",
  "exchange": "binanceusdm",
  "is_testnet": true,
  "api_key": "YOUR_BINANCE_API_KEY",
  "api_secret": "YOUR_BINANCE_SECRET_KEY",
  "params": {
    "symbol": "BTC/USDT:USDT",
    "side": "buy",
    "amount": 0.001,
    "price": 113757
  }
}
```

Acknowledge:
```json
{"status":"processing","action":"place_limit_order"}
```

Result:
```json
{"action":"place_limit_order","status":"filled","data":{…}}
```

## 4. Orderbook Streaming

### Start orderbook
```json
{"action": "start_orderbook", "exchange": "binanceusdm", "symbol": "BTC/USDT"}
```

### Stop orderbook
```json
{"action": "stop_orderbook"}
```

### Stop persistence to S3:
```json
{"action": "stop_orderbook_persistence"}
```




