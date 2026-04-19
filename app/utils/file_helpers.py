# -*- coding: utf-8 -*-
import os
from typing import Set, Dict
from dataclasses import dataclass


FILE_TYPE_EXTENSIONS: Dict[str, Set[str]] = {
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'},
    'document': {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.rtf', '.odt', '.ods', '.odp'},
    'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp'},
    'audio': {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma', '.ape', '.aiff'},
    'archive': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz'}
}

ALL_KNOWN_EXTENSIONS: Set[str] = set()
for exts in FILE_TYPE_EXTENSIONS.values():
    ALL_KNOWN_EXTENSIONS.update(exts)


def get_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    for ftype, extensions in FILE_TYPE_EXTENSIONS.items():
        if ext in extensions:
            return ftype
    return 'other'


def ensure_directory(path: str) -> str:
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def get_user_upload_folder(base_folder: str, user_id: int) -> str:
    folder = os.path.join(base_folder, f'user_{user_id}')
    return ensure_directory(folder)


def sanitize_filename(filename: str) -> str:
    dangerous_chars = ['/', '\\', '..', '\x00']
    result = filename
    for char in dangerous_chars:
        result = result.replace(char, '_')
    return result.strip()
