# -*- coding: utf-8 -*-
from .auth_controller import auth_bp, login_required
from .category_controller import category_bp
from .message_controller import message_bp, init_file_service

__all__ = [
    'auth_bp',
    'category_bp',
    'message_bp',
    'login_required',
    'init_file_service'
]
