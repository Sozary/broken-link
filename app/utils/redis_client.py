import redis
import ssl
from app.core.config import settings

def get_redis_client():
    if settings.REDIS_URL.startswith('rediss://'):
        return redis.Redis(
            connection_pool=redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                connection_class=redis.SSLConnection,
                ssl_cert_reqs=ssl.CERT_NONE
        )
    )
    else:
        return redis.Redis(
            connection_pool=redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        )