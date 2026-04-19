# -*- coding: utf-8 -*-
import bcrypt
from typing import Optional, Tuple
from ..repositories import UserRepository
from ..models import User


class AuthService:
    def __init__(self, user_repo: UserRepository = None):
        self._user_repo = user_repo or UserRepository()
    
    def register(self, username: str, password: str) -> Tuple[bool, str, Optional[int]]:
        if not username or not password:
            return False, '用户名和密码不能为空', None
        
        username = username.strip()
        
        if len(username) < 3 or len(username) > 50:
            return False, '用户名长度需要在3-50个字符之间', None
        
        if len(password) < 6:
            return False, '密码长度至少需要6个字符', None
        
        if self._user_repo.exists_by_username(username):
            return False, '用户名已存在', None
        
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
        
        try:
            user_id = self._user_repo.create(username, password_hash)
            return True, '注册成功，请登录', user_id
        except Exception:
            return False, '注册失败，请稍后重试', None
    
    def login(self, username: str, password: str) -> Tuple[bool, str, Optional[User]]:
        if not username or not password:
            return False, '用户名和密码不能为空', None
        
        user = self._user_repo.find_by_username(username.strip())
        
        if not user:
            return False, '用户名或密码错误', None
        
        if not bcrypt.checkpw(
            password.encode('utf-8'), 
            user.password_hash.encode('utf-8')
        ):
            return False, '用户名或密码错误', None
        
        return True, '登录成功', user
    
    def validate_user(self, user_id: int) -> Optional[User]:
        return self._user_repo.find_by_id(user_id)
