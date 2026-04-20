# -*- coding: utf-8 -*-
from typing import Optional, List
from .base import BaseRepository, get_beijing_time
from ..models import Category


class CategoryRepository(BaseRepository):
    def find_by_user(self, user_id: int) -> List[Category]:
        with self._get_cursor() as cursor:
            cursor.execute('''
                SELECT id, user_id, name, parent_id, created_at, is_deleted, deleted_at
                FROM categories 
                WHERE user_id = ? AND (is_deleted = 0 OR is_deleted IS NULL)
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
            created_at = get_beijing_time()
            cursor.execute('''
                INSERT INTO categories (user_id, name, parent_id, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, name, parent_id, created_at))
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
    
    def soft_delete(self, category_id: int, user_id: int) -> Optional[Category]:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM categories WHERE id = ? AND user_id = ?',
                (category_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            category = Category.from_row(row)
            deleted_at = get_beijing_time()
            
            cursor.execute(
                "UPDATE categories SET is_deleted = 1, deleted_at = ? WHERE id = ?",
                (deleted_at, category_id,)
            )
            cursor.execute(
                "UPDATE messages SET is_deleted = 1, deleted_at = ? WHERE category_id = ?",
                (deleted_at, category_id,)
            )
            cursor.connection.commit()
            return category
    
    def restore(self, category_id: int, user_id: int) -> Optional[Category]:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM categories WHERE id = ? AND user_id = ? AND is_deleted = 1',
                (category_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            category = Category.from_row(row)
            
            cursor.execute(
                "UPDATE categories SET is_deleted = 0, deleted_at = NULL WHERE id = ?",
                (category_id,)
            )
            cursor.execute(
                "UPDATE messages SET is_deleted = 0, deleted_at = NULL WHERE category_id = ?",
                (category_id,)
            )
            cursor.connection.commit()
            return category
    
    def permanent_delete(self, category_id: int, user_id: int) -> Optional[Category]:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM categories WHERE id = ? AND user_id = ?',
                (category_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            category = Category.from_row(row)
            
            cursor.execute('DELETE FROM messages WHERE category_id = ?', (category_id,))
            cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            cursor.connection.commit()
            return category
    
    def find_deleted(self, user_id: int) -> List[Category]:
        with self._get_cursor() as cursor:
            cursor.execute('''
                SELECT id, user_id, name, parent_id, created_at, is_deleted, deleted_at
                FROM categories 
                WHERE user_id = ? AND is_deleted = 1
                ORDER BY deleted_at DESC
            ''', (user_id,))
            return [Category.from_row(row) for row in cursor.fetchall()]
    
    def get_message_count(self, category_id: int) -> int:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) as count FROM messages WHERE category_id = ? AND (is_deleted = 0 OR is_deleted IS NULL)',
                (category_id,)
            )
            row = cursor.fetchone()
            return row['count'] if row else 0
