# -*- coding: utf-8 -*-
import time
from collections import defaultdict
from threading import Lock
from typing import Callable, Dict, Optional, Tuple
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter:
    _instance: Optional['RateLimiter'] = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._requests: Dict[str, list] = defaultdict(list)
                    cls._instance._blocked: Dict[str, float] = {}
        return cls._instance
    
    def is_allowed(
        self, 
        key: str, 
        max_requests: int, 
        window_seconds: int,
        block_duration: int = 300
    ) -> Tuple[bool, int, int]:
        current_time = time.time()
        
        if key in self._blocked:
            if current_time < self._blocked[key]:
                remaining = int(self._blocked[key] - current_time)
                return False, 0, remaining
            else:
                del self._blocked[key]
        
        self._requests[key] = [
            t for t in self._requests[key] 
            if current_time - t < window_seconds
        ]
        
        if len(self._requests[key]) >= max_requests:
            self._blocked[key] = current_time + block_duration
            return False, 0, block_duration
        
        self._requests[key].append(current_time)
        remaining = max_requests - len(self._requests[key])
        return True, remaining, 0
    
    def cleanup(self, window_seconds: int = 3600):
        current_time = time.time()
        keys_to_remove = []
        for key in list(self._requests.keys()):
            self._requests[key] = [
                t for t in self._requests[key]
                if current_time - t < window_seconds
            ]
            if not self._requests[key]:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._requests[key]
            self._blocked.pop(key, None)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limiter: RateLimiter = None):
        super().__init__(app)
        self._limiter = rate_limiter or RateLimiter()
        
        self._auth_limits = {
            ('POST', '/api/login'): (5, 60, 300),
            ('POST', '/api/register'): (3, 60, 300),
        }
        
        self._api_limits = {
            'default': (100, 60, 60),
        }
    
    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.client.host if request.client else 'unknown'
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        
        if path.startswith('/static/') or path in ['/', '/login', '/register', '/chat']:
            return await call_next(request)
        
        ip = self._get_client_ip(request)
        
        route_key = (method, path if '/api/' in path else None)
        
        if route_key in self._auth_limits:
            max_req, window, block = self._auth_limits[route_key]
            key = f"auth:{ip}:{path}"
            
            allowed, remaining, retry_after = self._limiter.is_allowed(
                key, max_req, window, block
            )
            
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        'detail': f'请求过于频繁，请 {retry_after} 秒后重试'
                    },
                    headers={
                        'Retry-After': str(retry_after),
                        'X-RateLimit-Remaining': '0'
                    }
                )
        
        else:
            max_req, window, block = self._api_limits['default']
            key = f"api:{ip}"
            
            allowed, remaining, retry_after = self._limiter.is_allowed(
                key, max_req, window, block
            )
            
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        'detail': '请求过于频繁，请稍后重试'
                    },
                    headers={
                        'Retry-After': str(retry_after),
                        'X-RateLimit-Remaining': str(remaining)
                    }
                )
        
        response = await call_next(request)
        response.headers['X-RateLimit-Remaining'] = str(remaining)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = (
            'accelerometer=(), camera=(), geolocation=(), '
            'gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()'
        )
        
        try:
            del response.headers['server']
        except KeyError:
            pass
        try:
            del response.headers['x-powered-by']
        except KeyError:
            pass
        
        return response


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={'detail': e.detail}
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
            
            return JSONResponse(
                status_code=500,
                content={'detail': '服务器内部错误，请稍后重试'}
            )
