from celery import Celery
import src.config as config

celery_app = Celery(
    'trading_tasks',
    broker=config.RABBITMQ_URL,
    backend='rpc://', # Using RPC for results via RabbitMQ
    include=['src.tasks.tasks']
)
