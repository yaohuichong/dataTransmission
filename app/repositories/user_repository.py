# -*- coding: utf-8 -*-
from typing import Optional, List
from .base import BaseRepository, DatabaseConnection
from ..models import User


class UserRepository(BaseRepository):
    def find_by_id(self, user_id: int) -> Optional[User]:
        with self._get_cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            return User.from_row(row)
    
    def find_by_username(self, username: str) -> Optional[User]:
        with self._get_cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            return User.from_row(row)
    
    def create(self, username: str, password_hash: str) -> int:
        with self._get_cursor() as cursor:
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            cursor.connection.commit()
            return cursor.lastrowid
    
    def exists_by_username(self, username: str) -> bool:
        with self._get_cursor() as cursor:
            cursor.execute('SELECT 1 FROM users WHERE username = ?', (username,))
            return cursor.fetchone() is not None
