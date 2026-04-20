# -*- coding: utf-8 -*-
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any, Dict
from contextlib import contextmanager
from abc import ABC, abstractmethod

BEIJING_TZ = timezone(timedelta(hours=8))


def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')


class DatabaseConnection:
    _instance: Optional['DatabaseConnection'] = None
    _db_path: str = ''
    
    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            if db_path:
                cls._db_path = db_path
        return cls._instance
    
    @classmethod
    def set_db_path(cls, db_path: str):
        cls._db_path = db_path
    
    @classmethod
    @contextmanager
    def get_connection(cls):
        conn = sqlite3.connect(cls._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    @classmethod
    def init_db(cls):
        with cls.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    parent_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (parent_id) REFERENCES categories(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    msg_type TEXT NOT NULL,
                    content TEXT,
                    filename TEXT,
                    saved_name TEXT,
                    file_size INTEGER,
                    relative_path TEXT,
                    folder_id TEXT,
                    file_count INTEGER,
                    category_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_user_time 
                ON messages(user_id, created_at)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_category 
                ON messages(user_id, category_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_folder 
                ON messages(folder_id, msg_type)
            ''')
            
            cursor.execute("PRAGMA table_info(messages)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'relative_path' not in columns:
                cursor.execute('ALTER TABLE messages ADD COLUMN relative_path TEXT')
            if 'folder_id' not in columns:
                cursor.execute('ALTER TABLE messages ADD COLUMN folder_id TEXT')
            if 'file_count' not in columns:
                cursor.execute('ALTER TABLE messages ADD COLUMN file_count INTEGER')
            if 'category_id' not in columns:
                cursor.execute('ALTER TABLE messages ADD COLUMN category_id INTEGER')
            if 'is_deleted' not in columns:
                cursor.execute('ALTER TABLE messages ADD COLUMN is_deleted INTEGER DEFAULT 0')
            if 'deleted_at' not in columns:
                cursor.execute('ALTER TABLE messages ADD COLUMN deleted_at DATETIME')
            
            cursor.execute("PRAGMA table_info(categories)")
            cat_columns = [col[1] for col in cursor.fetchall()]
            if 'is_deleted' not in cat_columns:
                cursor.execute('ALTER TABLE categories ADD COLUMN is_deleted INTEGER DEFAULT 0')
            if 'deleted_at' not in cat_columns:
                cursor.execute('ALTER TABLE categories ADD COLUMN deleted_at DATETIME')
            
            conn.commit()


class BaseRepository(ABC):
    def __init__(self, db: DatabaseConnection = None):
        self._db = db or DatabaseConnection()
    
    @contextmanager
    def _get_cursor(self):
        with self._db.get_connection() as conn:
            yield conn.cursor()
