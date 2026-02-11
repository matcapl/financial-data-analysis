# """
# Rate limiting middleware for API endpoints
# """

# import time
# from typing import Dict, List
# from fastapi import Request, HTTPException
# from starlette.middleware.base import BaseHTTPMiddleware
# from starlette.responses import Response


# class RateLimiter:
#     """Simple in-memory rate limiter"""
    
#     def __init__(self, requests_per_minute: int = 60):
#         self.requests_per_minute = requests_per_minute
#         self.requests: Dict[str, List[float]] = {}
    
#     def is_allowed(self, client_ip: str) -> bool:
#         """Check if request is allowed based on rate limit"""
#         current_time = time.time()
        
#         # Clean old requests
#         if client_ip in self.requests:
#             self.requests[client_ip] = [
#                 req_time for req_time in self.requests[client_ip]
#                 if current_time - req_time < 60  # Keep only requests from last minute
#             ]
#         else:
#             self.requests[client_ip] = []
        
#         # Check if under limit
#         if len(self.requests[client_ip]) >= self.requests_per_minute:
#             return False
        
#         # Add current request
#         self.requests[client_ip].append(current_time)
#         return True


# class RateLimitMiddleware(BaseHTTPMiddleware):
#     """FastAPI middleware for rate limiting"""
    
#     def __init__(self, app, requests_per_minute: int = 60):
#         super().__init__(app)
#         self.rate_limiter = RateLimiter(requests_per_minute)
    
#     async def dispatch(self, request: Request, call_next) -> Response:
#         # Skip rate limiting for health checks
#         if request.url.path in ["/health", "/api/monitoring/metrics/health"]:
#             return await call_next(request)
        
#         client_ip = request.client.host if request.client else "unknown"
        
#         if not self.rate_limiter.is_allowed(client_ip):
#             raise HTTPException(
#                 status_code=429,
#                 detail="Too many requests. Please try again later."
#             )
        
#         return await call_next(request)

import time
from typing import Dict, List
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class RateLimiter:
    def __init__(self, requests_per_minute: int = 300):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        window = 60

        requests = self.requests.setdefault(client_ip, [])
        requests[:] = [t for t in requests if now - t < window]

        if len(requests) >= self.requests_per_minute:
            return False

        requests.append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 300):
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute)

    async def dispatch(self, request: Request, call_next) -> Response:

        # Skip rate limiting for demo endpoints
        if request.url.path.startswith("/api/demo"):
            return await call_next(request)

        # ✅ Only rate-limit API routes
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        if not self.limiter.is_allowed(client_ip):
            # ✅ Never crash the server from middleware
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )

        return await call_next(request)
