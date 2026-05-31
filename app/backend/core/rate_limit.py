import os
from slowapi import Limiter
from slowapi.util import get_remote_address

RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"

if RATELIMIT_ENABLED:
    limiter = Limiter(key_func=get_remote_address)
else:
    class NoOpLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    limiter = NoOpLimiter()
