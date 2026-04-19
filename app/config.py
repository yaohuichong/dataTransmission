# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass, field
from typing import Set, Dict


@dataclass
class Config:
    SECRET_KEY: str = 'file-transfer-helper-secret-key-2024'
    MAX_CONTENT_LENGTH: int = 500 * 1024 * 1024
    DATABASE: str = None
    UPLOAD_FOLDER: str = None
    CHUNK_SIZE: int = 64 * 1024
    STREAM_BUFFER_SIZE: int = 64 * 1024
    
    FILE_TYPE_EXTENSIONS: Dict[str, Set[str]] = field(default_factory=lambda: {
        'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'},
        'document': {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.rtf', '.odt', '.ods', '.odp'},
        'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp'},
        'audio': {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma', '.ape', '.aiff'},
        'archive': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz'}
    })
    
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
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')


class TestingConfig(Config):
    DEBUG = True
    TESTING = True


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}


def get_config(env_name: str = None) -> Config:
    if env_name is None:
        env_name = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env_name, DevelopmentConfig)()
