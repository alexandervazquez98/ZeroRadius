from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _get_real_ip(request: Request) -> str:
    """
    Read client IP from X-Forwarded-For (nginx sets this).
    Takes the FIRST element — nginx appends its own IP at the end.
    Falls back to direct connection IP if header is absent.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_real_ip, storage_uri="memory://")
