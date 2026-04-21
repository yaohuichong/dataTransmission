# -*- coding: utf-8 -*-
import os
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from .config import Config, get_config
from .repositories import DatabaseConnection
from .controllers import auth_router, category_router, message_router, init_file_service
from .middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    ExceptionHandlerMiddleware
)
from .websocket_manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def create_app(config: Config = None) -> FastAPI:
    if config is None:
        config = get_config()
    
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None
    )
    
    app.add_middleware(ExceptionHandlerMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    
    if config.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.CORS_ORIGINS,
            allow_credentials=config.CORS_ALLOW_CREDENTIALS,
            allow_methods=config.CORS_ALLOW_METHODS,
            allow_headers=config.CORS_ALLOW_HEADERS,
        )
    
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.SECRET_KEY,
        session_cookie=config.SESSION_COOKIE_NAME,
        max_age=config.SESSION_MAX_AGE,
        same_site='lax',
        https_only=not config.DEBUG if hasattr(config, 'DEBUG') else False
    )
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=templates_dir)
    
    def url_for(name: str, **kwargs) -> str:
        if name == 'static':
            filename = kwargs.get('filename', '')
            return f"/static/{filename}"
        route_map = {
            'login_page': '/login',
            'register_page': '/register',
            'chat': '/chat',
            'index': '/',
        }
        return route_map.get(name, f'/{name}')
    
    templates.env.globals['url_for'] = url_for
    
    app.state.config = config
    app.state.templates = templates
    
    DatabaseConnection.set_db_path(config.DATABASE)
    DatabaseConnection.init_db()
    
    if not os.path.exists(config.UPLOAD_FOLDER):
        os.makedirs(config.UPLOAD_FOLDER)
    
    init_file_service(
        upload_folder=config.UPLOAD_FOLDER,
        max_file_size=config.MAX_FILE_SIZE,
        blocked_extensions=config.BLOCKED_EXTENSIONS,
        ws_manager=ws_manager
    )
    
    app.include_router(auth_router)
    app.include_router(category_router)
    app.include_router(message_router)
    
    return app


from .config import Config, get_config, DevelopmentConfig, ProductionConfig, TestingConfig

__all__ = [
    'create_app',
    'Config',
    'get_config',
    'DevelopmentConfig',
    'ProductionConfig',
    'TestingConfig'
]
