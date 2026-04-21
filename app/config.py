# -*- coding: utf-8 -*-
import os
import secrets
from dataclasses import dataclass, field
from typing import Set, Dict, Optional, List


@dataclass
class Config:
    SECRET_KEY: str = field(default_factory=lambda: secrets.token_hex(32))
    MAX_CONTENT_LENGTH: int = 0
    MAX_FILE_SIZE: int = 0
    DATABASE: str = None
    UPLOAD_FOLDER: str = None
    CHUNK_SIZE: int = 64 * 1024
    STREAM_BUFFER_SIZE: int = 64 * 1024
    SESSION_COOKIE_NAME: str = 'session'
    SESSION_MAX_AGE: int = 60 * 60 * 24 * 7
    
    FILE_TYPE_EXTENSIONS: Dict[str, Set[str]] = field(default_factory=lambda: {
        'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'},
        'document': {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.rtf', '.odt', '.ods', '.odp'},
        'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp'},
        'audio': {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma', '.ape', '.aiff'},
        'archive': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz'}
    })
    
    BLOCKED_EXTENSIONS: Set[str] = field(default_factory=set)
    
    ALLOWED_MIME_TYPES: Set[str] = field(default_factory=lambda: {
        'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
        'image/svg+xml', 'image/tiff', 'image/x-icon',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain', 'text/markdown', 'text/csv',
        'video/mp4', 'video/x-msvideo', 'video/x-matroska', 'video/quicktime',
        'video/x-ms-wmv', 'video/webm', 'video/x-flv',
        'audio/mpeg', 'audio/wav', 'audio/flac', 'audio/aac', 'audio/ogg',
        'audio/x-ms-wma', 'audio/x-aiff',
        'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
        'application/x-tar', 'application/gzip', 'application/x-bzip2',
        'application/octet-stream'
    })
    
    CORS_ORIGINS: List[str] = field(default_factory=list)
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = field(default_factory=lambda: ['GET', 'POST', 'PUT', 'DELETE'])
    CORS_ALLOW_HEADERS: List[str] = field(default_factory=lambda: ['*'])
    
    def __post_init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if self.DATABASE is None:
            self.DATABASE = os.path.join(base_dir, 'database.sqlite')
        if self.UPLOAD_FOLDER is None:
            self.UPLOAD_FOLDER = os.path.join(base_dir, 'uploads')
    
    @property
    def ALL_KNOWN_EXTENSIONS(self) -> Set[str]:
        extensions = set()
        for exts in self.FILE_TYPE_EXTENSIONS.values():
            extensions.update(exts)
        return extensions


class DevelopmentConfig(Config):
    DEBUG: bool = True
    TESTING: bool = False


class ProductionConfig(Config):
    DEBUG: bool = False
    TESTING: bool = False
    
    def __post_init__(self):
        super().__post_init__()
        env_secret = os.environ.get('SECRET_KEY')
        if not env_secret:
            raise ValueError(
                "生产环境必须设置 SECRET_KEY 环境变量！\n"
                "请运行: export SECRET_KEY=$(python -c \"import secrets; print(secrets.token_hex(32))\")"
            )
        self.SECRET_KEY = env_secret
        
        cors_origins = os.environ.get('CORS_ORIGINS', '')
        if cors_origins:
            self.CORS_ORIGINS = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]


class TestingConfig(Config):
    DEBUG: bool = True
    TESTING: bool = True


_config_instance: Config = None


def get_config(env: str = None) -> Config:
    global _config_instance
    
    if _config_instance is not None:
        return _config_instance
    
    if env is None:
        env = os.environ.get('APP_ENV', 'development')
    
    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig
    }
    
    config_class = config_map.get(env, DevelopmentConfig)
    _config_instance = config_class()
    return _config_instance
