# -*- coding: utf-8 -*-
from .auth_controller import auth_router, login_required
from .category_controller import category_router
from .message_controller import message_router, init_file_service

__all__ = [
    'auth_router',
    'category_router',
    'message_router',
    'login_required',
    'init_file_service'
]
