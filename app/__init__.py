# -*- coding: utf-8 -*-
import os
from flask import Flask, request
from .config import Config, get_config
from .repositories import DatabaseConnection
from .controllers import auth_bp, category_bp, message_bp, init_file_service


def create_app(config: Config = None) -> Flask:
    if config is None:
        config = get_config()
    
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static'
    )
    
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    app.config['DATABASE'] = config.DATABASE
    app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
    
    DatabaseConnection.set_db_path(config.DATABASE)
    DatabaseConnection.init_db()
    
    if not os.path.exists(config.UPLOAD_FOLDER):
        os.makedirs(config.UPLOAD_FOLDER)
    
    init_file_service(config.UPLOAD_FOLDER)
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(message_bp)
    
    @app.after_request
    def add_cache_headers(response):
        if 'static' in request.path or request.path.endswith(
            ('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2', '.ttf', '.eot')
        ):
            response.cache_control.max_age = 86400
            response.cache_control.public = True
        return response
    
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response
    
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
