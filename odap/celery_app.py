"""Celery配置和任务定义"""

from celery import Celery
from odap.infra.config_composer import get_config

# Redis URL配置
# 在Docker环境中使用 docker-compose.yml 中定义的 graphiti-cache 服务
# 在本地开发时可以使用 localhost:6379
REDIS_URL = get_config("cache.redis_url", 'redis://localhost:6379/0')

# 创建Celery应用
celery_app = Celery(
    'odap',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['odap.tasks']
)

# 配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
)

if __name__ == '__main__':
    celery_app.start()