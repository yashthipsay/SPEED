# SPEED(Smart Protocol for Efficient Execution & Delivery) – Documentation & User Guide

Welcome to the documentation for the **Smart Protocol for Efficient Execution & Delivery**. This platform provides high-performance, modular interaction with multiple centralized cryptocurrency exchanges, supporting advanced market data retrieval, trade execution, symbol mapping, and historical data persistence for research and backtesting.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Setup & Dependencies](#setup--dependencies)
3. [System Architecture Overview](#system-architecture-overview)
4. [Task Walkthroughs](#task-walkthroughs)
    - [Task 1: Modular Exchange Data Connectors](#task-1-modular-exchange-data-connectors)
    - [Task 2: Trade Execution & Order Management](#task-2-trade-execution--order-management)
    - [Task 3: Position & PnL Monitoring](#task-3-position--pnl-monitoring)
    - [Task 4: Universal Symbol Mapper](#task-4-universal-symbol-mapper)
    - [Task 5: Historical Data Persistence for Backtesting](#task-5-historical-data-persistence-for-backtesting)
5. [Running the System: Step-by-Step Guide](#running-the-system-step-by-step-guide)
6. [Stress Testing: Benchmarking Throughput](#stress-testing-benchmarking-throughput)
7. [Symbol Mapper: Standardization Utility](#symbol-mapper-standardization-utility)
8. [Additional Resources and Tips](#additional-resources-and-tips)

## Project Overview

This engine is designed for quantitative researchers and high-volume traders requiring unified, low-latency access to a variety of digital asset venues. Its modular connectors, robust trading execution framework, and seamless data persistence workflows make it a compelling base for both production and research workflows.

## Setup & Dependencies

### 1. Clone the Repository

```bash
git clone 
cd 
```

### 2. Install Dependencies

A `requirements.txt` is provided:

```bash
pip install -r requirements.txt
```

**Notable dependencies:**  
- [`ccxt`](https://github.com/ccxt/ccxt): Multi-exchange trading library
- `celery`, `pika`, `aio-pika`: For async task management and messaging
- `boto3`, `pyarrow`, `pandas`: For efficient S3/Parquet data management
- `fastapi`, `uvicorn`: For a WebSocket-enabled HTTP server
- `websockets`, `aiohttp`: For client-server real-time communication

### 3. Start RabbitMQ via Docker

```bash
docker run -d --hostname my-rabbit --name some-rabbit -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

This exposes AMPQ at `amqp://guest:guest@localhost:5672/` – make sure your `config.py` points to this URL.

## System Architecture Overview

```plaintext
┌───────────────┐      ┌───────────────┐      ┌─────────────────┐
│ Trading       │      │ Celery        │      │ Data Persistent │
│ Clients (WS)  │─────▶│ Worker        │─────▶│ S3 (Parquet)    │
└──────┬────────┘      └──────▲────────┘      └─────────────────┘
       │                        │
       │FastAPI/WebSocket       │RabbitMQ Fanout
┌──────▼────────┐      ┌────────┴──────┐
│   Websocket   │◀─────│ Unified       │
│   Server      │      │ Exchange API  │
└───────────────┘      └───────────────┘
```

- **Trading Clients:** Human/automated clients connect via terminal UI or programmatically.
- **WebSocket/API server:** Proxies requests to Celery asynchronous workers, handles real-time updates.
- **Celery Workers:** Perform heavy tasks—order placement, market fetching, persistence.
- **S3 Storage:** For high-frequency order book backups in ultra-efficient Parquet files.
- **RabbitMQ:** Provides loose coupling via message passing/broadcasting for scalable notification.

## Task Walkthroughs

### Task 1: Modular Exchange Data Connectors

Implemented in: `unified_exchange.py`, `symbol_mapper.py`

- Modular connectors for **Binance (coinm/usdm), Kucoin, Bitmart, Deribit, OKX**.
- Exposes:
    - Best Bid & Ask fetchers
    - L2 Order Book collectors (10+ levels deep)
    - Funding Rate (current, predicted, historical, APR computed)
    - Price Impact Estimation for order execution

**How it works:**  
All functions are exposed via the UnifiedExchangeAPI class. Additional exchanges can be easily integrated adding them to `symbol_mapper.py` and implementing wrappers in `unified_exchange.py`.

### Task 2: Trade Execution & Order Management

Implemented in: `server.py`, `tasks.py`, `unified_exchange.py`

- Place/cancel/track orders via a **unified function** (market or limit).
- Handles credentials (incl. password support for OKX, KuCoin, etc).
- Order status tracked: `OPEN`, `FILLED`, `CANCELED`, `REJECTED`, etc.
- **Performance:** Supports rapid submission and atomic cancellation, tested with hundreds of concurrent clients.

**API usage:**  
See example commands in the [Step-by-Step](#running-the-system-step-by-step-guide) section.

### Task 3: Position & PnL Monitoring

Implemented in: `tasks.py`, `unified_exchange.py`

- Given a filled `OrderID`, monitors and returns live PnL:
    - Account, pair, side, entry, quantity, and NetPnL (real-time calculated)
- Pushes updates to users via WebSocket (RabbitMQ broadcast).

**Customization:**  
Patched for per-exchange detail (contract size, symbol resolution).

### Task 4: Universal Symbol Mapper

Implemented in: `symbol_mapper.py`

- Maps all exchange-specific symbols to a **universal, normalized format** (`BTC/USDT`).
- Handles common quirks: hyphens, colons, contract suffixes, quote currency variations.
- CLI utility to generate mappings and explore both directions.

### Task 5: Historical Data Persistence for Backtesting

Implemented in: `tasks.py`, `data_persistor.py`

- Periodically fetches L2 orderbook using highly-configurable intervals.
- Data written as **Parquet files partitioned by date and pair** in S3.
- Schema: timestamp, exchange, symbol, bids, asks.

## Running the System: Step-by-Step Guide

### 1. Start RabbitMQ (if not already running):

```bash
docker run -d --hostname my-rabbit --name some-rabbit -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the WebSocket Server

```bash
uvicorn server:app --host localhost --port 8765 --reload
```

### 4. Start the Celery Worker

```bash
# ensure the root dir is on PYTHONPATH so `src` is importable
# Enter the command below in the same terminal as the queue, before starting the queue
export PYTHONPATH=$(pwd)
# Start the queue
celery -A src.celery_app:celery_app worker --loglevel=info --concurrency=16
```

### 5. Launch the Terminal Trading Client (Recommended only for orderbook)

```bash
python -m clients.trading_client trader_alpha --account_name yash
```
#### Use postman client for placing orders, while you view the order book on your Terminal Trading Client.

![alt text](images/postman_client.png)

### 6. Start Orderbook Capture

In the terminal client, enter:
```json
{"action": "start_orderbook", "exchange": "binanceusdm", "symbol": "XLM/USDT"}
```
You will see the live orderbook begin populating.

### 7. Stop Orderbook or Persistence

To stop UI only (orderbook streaming):
```json
{"action": "stop_orderbook"}
```
To stop persistent recording to S3:
```json
{"action": "stop_orderbook_persistence"}
```

**Your S3 bucket will begin receiving regularly timestamped Parquet files for the selected trading pair, enabling robust backtesting.**

## Stress Testing: Benchmarking Throughput

### Stress test with 200 concurrent clients & orders

To run the high-concurrency test:
```bash
python -m clients.stress_test
```
- This script will:
    - Spawn 200 WebSocket clients.
    - Each places an order, attempts immediate cancellation, and logs execution.
    - At the end, prints:
        - Total clients, success/failure counts, average execution/cancellation time.

You can modify exchanges, credentials, and symbols in the `TEST_ACCOUNTS` array within `stress_test.py` for your environment.

### 📊 Stress Test Results (BinanceUSDM & BinanceCOINM)

<!-- vertical layout, one below the other -->
**Stress Test 1**  
![Stress Test 1](images/stress_test_1_bnb.png)  

**Stress Test 2**  
![Stress Test 2](images/stress_test_2_bnb.png)  

**Stress Test 3**  
![Stress Test 3](images/stress_test_3_bnb.png)  

---

### 📊 Stress Test 4: OKX & Binance (USDM & COINM) Combined (100 Orders)

Running 200 concurrent orders on OKX + Binance triggered rate limits, so we reduced to **100** clients:

**Stress Test 4 Results**  
![Stress Test 4 OKX & Binance](images/stress_test_4_bnb_okx.png)  

---

### 📊 Deribit Stress Test (50 Orders) & Timeout Tuning

Deribit’s matching is relatively slower. We ran **50** concurrent clients:

- With the default **30 s** WebSocket timeout, many fills appeared as failures (false negatives):

  **30 s Timeout – Many False Negatives**  
  ![Deribit Failures (30s Timeout)](images/deribit_tests_failing.png)  

- After extending the WebSocket recv timeout to **120 s**, all orders passed, yielding accurate data:

  **120 s Timeout – All Orders Filled**  
  ![Deribit Success (120s Timeout)](images/deribit_stress_test_success.png)  

## Symbol Mapper: Standardization Utility

### Generate and Explore Exchange Symbol Mappings

Normalize symbol IDs between any supported exchange and the universal format:

```bash
python3 symbol_mapper.py
```

- Will fetch and cache all supported exchange market symbols into a JSON file.
- Test both `to_exchange_specific` and `to_universal` mappings interactively.
- Modify/add exchanges at the top of `symbol_mapper.py` as needed.

## Additional Resources and Tips

- **Order Placement & Tracking:**  
  - All trading actions (market/limit orders, analysis) are routed via WebSocket commands in JSON format, which are handled asynchronously and results streamed back via the same channel.
- **Adding More Exchanges:**  
  - You only need to add the exchange to the `exchanges_to_fetch` array in `symbol_mapper.py` and ensure your CCXT credentials/configuration are accurate.
- **Error Handling:**  
  - Detailed logs are printed for all failures; errors are also broadcast back to the client for UI notification.
- **Backtesting/Research:**  
  - Use the S3 Parquet database for rapid data frame loading and market simulation.
