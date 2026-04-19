# -*- coding: utf-8 -*-
from typing import Optional, List
from .base import BaseRepository
from ..models import Category


class CategoryRepository(BaseRepository):
    def find_by_user(self, user_id: int) -> List[Category]:
        with self._get_cursor() as cursor:
            cursor.execute('''
                SELECT id, name, parent_id 
                FROM categories 
                WHERE user_id = ?
                ORDER BY created_at ASC
            ''', (user_id,))
            return [Category.from_row(row) for row in cursor.fetchall()]
    
    def find_by_id(self, category_id: int, user_id: int) -> Optional[Category]:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM categories WHERE id = ? AND user_id = ?',
                (category_id, user_id)
            )
            row = cursor.fetchone()
            return Category.from_row(row)
    
    def create(self, user_id: int, name: str, parent_id: Optional[int] = None) -> int:
        with self._get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO categories (user_id, name, parent_id)
                VALUES (?, ?, ?)
            ''', (user_id, name, parent_id))
            cursor.connection.commit()
            return cursor.lastrowid
    
    def update(self, category_id: int, name: str) -> bool:
        with self._get_cursor() as cursor:
            cursor.execute(
                'UPDATE categories SET name = ? WHERE id = ?',
                (name, category_id)
            )
            cursor.connection.commit()
            return cursor.rowcount > 0
    
    def delete(self, category_id: int) -> bool:
        with self._get_cursor() as cursor:
            cursor.execute(
                'UPDATE messages SET category_id = NULL WHERE category_id = ?',
                (category_id,)
            )
            cursor.execute(
                'UPDATE categories SET parent_id = NULL WHERE parent_id = ?',
                (category_id,)
            )
            cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            cursor.connection.commit()
            return cursor.rowcount > 0
