# Victor da Cunha
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import re


class IPAccessMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_origins):
        super().__init__(app)
        self.allowed_hosts = []
        for origin in allowed_origins:
            if not origin or origin.strip() == "":
                continue
            origin = origin.strip()
            if origin == "*":
                self.allow_all = True
                return
            if origin.startswith("http://") or origin.startswith("https://"):
                hostname = re.sub(r'^https?://', '', origin).split('/')[0]
                self.allowed_hosts.append(hostname)
            else:
                self.allowed_hosts.append(origin)
        if "127.0.0.1" not in self.allowed_hosts:
            self.allowed_hosts.append("127.0.0.1")
        if "localhost" not in self.allowed_hosts:
            self.allowed_hosts.append("localhost")
        self.allow_all = False

    async def dispatch(self, request: Request, call_next):
        client_host = request.client.host if request.client else None
        if self.allow_all:
            response = await call_next(request)
            return response
        if client_host and client_host not in self.allowed_hosts:
            return Response(content="Access denied: Host not allowed", status_code=403, media_type="text/plain")
        response = await call_next(request)
        return response
