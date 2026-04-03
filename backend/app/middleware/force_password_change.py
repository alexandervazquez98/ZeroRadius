import jwt
from jwt.exceptions import InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.security import SECRET_KEY, ALGORITHM

# Paths that are allowed even when force_change is True
_ALLOWED_PATHS = {
    "/auth/token",
    "/auth/change-password",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class ForcePasswordChangeMiddleware(BaseHTTPMiddleware):
    """Block all requests (except auth endpoints) when JWT contains force_change=True."""

    async def dispatch(self, request: Request, call_next):
        # Skip check for allowed paths
        path = request.url.path
        if any(
            path == allowed or path.startswith(allowed) for allowed in _ALLOWED_PATHS
        ):
            return await call_next(request)

        # Skip if no Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        token = auth_header[7:]
        secret_key = SECRET_KEY
        algorithm = ALGORITHM

        try:
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            if payload.get("force_change", False):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Password change required. Please change your password before accessing this resource."
                    },
                )
        except (InvalidTokenError, Exception):
            # Let FastAPI's security handle invalid tokens
            pass

        return await call_next(request)
