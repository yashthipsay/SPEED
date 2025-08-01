* python trading_client.py trader_alpha

* uvicorn server:app --host localhost --port 8765 --reload

* docker run -d --name speed-trading -p 5672:5672 -p 15672:15672 rabbitmq:3-management

* export PYTHONPATH=$(pwd)

* celery -A celery_app:celery_app worker --loglevel=info