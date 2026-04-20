# -*- coding: utf-8 -*-
from .file_helpers import (
    FILE_TYPE_EXTENSIONS,
    ALL_KNOWN_EXTENSIONS,
    get_file_type,
    ensure_directory,
    get_user_upload_folder,
    sanitize_filename
)

__all__ = [
    'FILE_TYPE_EXTENSIONS',
    'ALL_KNOWN_EXTENSIONS',
    'get_file_type',
    'ensure_directory',
    'get_user_upload_folder',
    'sanitize_filename'
]


def stream_file(filepath: str, chunk_size: int = 64 * 1024):
    from .streaming import stream_file as _stream_file
    return _stream_file(filepath, chunk_size)


def stream_zip_directory(folder_path: str, chunk_size: int = 64 * 1024):
    from .streaming import stream_zip_directory as _stream_zip_directory
    return _stream_zip_directory(folder_path, chunk_size)


def stream_tar_directory(folder_path: str, chunk_size: int = 64 * 1024):
    from .streaming import stream_tar_directory as _stream_tar_directory
    return _stream_tar_directory(folder_path, chunk_size)


def true_streaming_zip(folder_path: str, chunk_size: int = 64 * 1024):
    from .streaming import true_streaming_zip as _true_streaming_zip
    return _true_streaming_zip(folder_path, chunk_size)


CHUNK_SIZE = 64 * 1024
