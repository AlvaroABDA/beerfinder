import time
from collections import defaultdict
from flask import request, session

# Almacén ligero en memoria por proceso (puede delegarse a Redis en despliegue multi-réplica)
_BUCKETS = defaultdict(list)


def client_identifier():
    uid = session.get('user_id')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
    return f"u:{uid}" if uid else f"ip:{ip}"


def check_rate_limit(action_key, limit=10, window_seconds=300):
    """Devuelve True si la petición está dentro del límite permitido, False si excede."""
    now = time.time()
    key = f"{action_key}:{client_identifier()}"
    timestamps = [t for t in _BUCKETS[key] if now - t < window_seconds]
    if len(timestamps) >= limit:
        _BUCKETS[key] = timestamps
        return False
    timestamps.append(now)
    _BUCKETS[key] = timestamps
    return True


def apply_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    return response

