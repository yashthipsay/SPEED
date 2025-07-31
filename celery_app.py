from celery import Celery
import config

celery_app = Celery(
    'trading_tasks',
    broker=config.RABBITMQ_URL,
    backend='rpc://', # Using RPC for results via RabbitMQ
    include=['tasks']
)
