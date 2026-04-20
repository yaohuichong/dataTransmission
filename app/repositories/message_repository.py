# -*- coding: utf-8 -*-
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from .base import BaseRepository, get_beijing_time
from ..models import Message
from ..utils import FILE_TYPE_EXTENSIONS, ALL_KNOWN_EXTENSIONS


@dataclass
class MessageSearchParams:
    user_id: int
    keyword: str = ''
    category_name: str = ''
    file_type: str = ''
    date: str = ''
    start_date: str = ''
    end_date: str = ''
    since: str = '0'
    category_id: int = None


class MessageRepository(BaseRepository):
    def find_by_id(self, msg_id: int, user_id: int) -> Optional[Message]:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM messages WHERE id = ? AND user_id = ?',
                (msg_id, user_id)
            )
            row = cursor.fetchone()
            return Message.from_row(row)
    
    def find_messages(self, user_id: int, since: str = '0', category_id: int = None) -> List[Message]:
        with self._get_cursor() as cursor:
            query = '''
                SELECT id, user_id, msg_type, content, filename, saved_name, file_size, relative_path, 
                       folder_id, file_count, category_id, is_deleted, deleted_at, created_at
                FROM messages 
                WHERE user_id = ? AND id > ? AND msg_type != 'folder_file' AND (is_deleted = 0 OR is_deleted IS NULL)
            '''
            params = [user_id, since]
            
            if category_id:
                query += ' AND category_id = ?'
                params.append(category_id)
            
            query += ' ORDER BY created_at ASC'
            
            cursor.execute(query, params)
            return [Message.from_row(row) for row in cursor.fetchall()]
    
    def search(self, params: MessageSearchParams) -> List[Dict[str, Any]]:
        with self._get_cursor() as cursor:
            query = '''
                SELECT m.id, m.msg_type, m.content, m.filename, m.file_size, 
                       m.relative_path, m.folder_id, m.file_count, m.category_id, 
                       m.created_at, 
                       c.name as category_name
                FROM messages m 
                LEFT JOIN categories c ON m.category_id = c.id
                WHERE m.user_id = ? AND m.msg_type != 'folder_file' AND (m.is_deleted = 0 OR m.is_deleted IS NULL)
            '''
            sql_params = [params.user_id]
            
            if params.keyword:
                query += ' AND (m.content LIKE ? OR m.filename LIKE ? OR m.relative_path LIKE ?)'
                keyword_pattern = f'%{params.keyword}%'
                sql_params.extend([keyword_pattern, keyword_pattern, keyword_pattern])
            
            if params.category_name:
                category_names = [name.strip() for name in params.category_name.split(',') if name.strip()]
                if len(category_names) == 1:
                    query += ' AND c.name = ?'
                    sql_params.append(category_names[0])
                elif len(category_names) > 1:
                    placeholders = ' OR '.join(['c.name = ?' for _ in category_names])
                    query += f' AND ({placeholders})'
                    for name in category_names:
                        sql_params.append(name)
            
            if params.file_type:
                if params.file_type == 'text':
                    query += " AND m.msg_type = 'text'"
                elif params.file_type == 'folder':
                    query += " AND m.msg_type = 'folder'"
                elif params.file_type in FILE_TYPE_EXTENSIONS:
                    extensions = FILE_TYPE_EXTENSIONS[params.file_type]
                    placeholders = ' OR '.join(['m.filename LIKE ?' for _ in extensions])
                    query += f" AND m.msg_type = 'file' AND ({placeholders})"
                    sql_params.extend([f'%{ext}' for ext in extensions])
                elif params.file_type == 'other':
                    placeholders = ' OR '.join(['m.filename LIKE ?' for _ in ALL_KNOWN_EXTENSIONS])
                    query += f" AND m.msg_type = 'file' AND NOT ({placeholders})"
                    sql_params.extend([f'%{ext}' for ext in ALL_KNOWN_EXTENSIONS])
            
            if params.date:
                query += ' AND DATE(m.created_at) = ?'
                sql_params.append(params.date)
            
            if params.start_date:
                query += ' AND DATE(m.created_at) >= ?'
                sql_params.append(params.start_date)
            
            if params.end_date:
                query += ' AND DATE(m.created_at) <= ?'
                sql_params.append(params.end_date)
            
            query += ' ORDER BY m.created_at DESC LIMIT 100'
            
            cursor.execute(query, sql_params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                result = {
                    'id': row['id'],
                    'type': row['msg_type'],
                    'time': row['created_at'],
                    'category_id': row['category_id'],
                    'category_name': row['category_name'] or ''
                }
                if row['msg_type'] == 'text':
                    result['content'] = row['content']
                elif row['msg_type'] == 'folder':
                    result['filename'] = row['filename']
                    result['file_size'] = row['file_size']
                    result['folder_id'] = row['folder_id']
                    result['file_count'] = row['file_count']
                else:
                    result['filename'] = row['filename']
                    result['file_size'] = row['file_size']
                    result['file_id'] = row['id']
                    result['relative_path'] = row['relative_path'] or ''
                results.append(result)
            
            return results
    
    def create_text_message(self, user_id: int, content: str, category_id: int = None) -> Tuple[int, str]:
        with self._get_cursor() as cursor:
            created_at = get_beijing_time()
            cursor.execute('''
                INSERT INTO messages (user_id, msg_type, content, category_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 'text', content, category_id, created_at))
            msg_id = cursor.lastrowid
            cursor.connection.commit()
            return msg_id, created_at
    
    def create_file_message(
        self, user_id: int, filename: str, saved_name: str, 
        file_size: int, relative_path: str = '', category_id: int = None
    ) -> Tuple[int, str]:
        with self._get_cursor() as cursor:
            created_at = get_beijing_time()
            cursor.execute('''
                INSERT INTO messages (user_id, msg_type, filename, saved_name, file_size, relative_path, category_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 'file', filename, saved_name, file_size, relative_path, category_id, created_at))
            msg_id = cursor.lastrowid
            cursor.connection.commit()
            return msg_id, created_at
    
    def create_folder_message(
        self, user_id: int, folder_name: str, folder_path: str,
        folder_id: str, total_size: int, file_count: int, category_id: int = None
    ) -> Tuple[int, str]:
        with self._get_cursor() as cursor:
            created_at = get_beijing_time()
            cursor.execute('''
                INSERT INTO messages (user_id, msg_type, filename, saved_name, file_size, folder_id, file_count, category_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 'folder', folder_name, folder_path, total_size, folder_id, file_count, category_id, created_at))
            msg_id = cursor.lastrowid
            cursor.connection.commit()
            return msg_id, created_at
    
    def batch_create_folder_files(
        self, user_id: int, folder_id: str, files: List[Dict[str, Any]]
    ) -> int:
        with self._get_cursor() as cursor:
            created_at = get_beijing_time()
            data = [
                (
                    user_id, 'folder_file', 
                    f['filename'], f['saved_name'], f['file_size'],
                    f['relative_path'], folder_id, len(files), created_at
                )
                for f in files
            ]
            cursor.executemany('''
                INSERT INTO messages (user_id, msg_type, filename, saved_name, file_size, relative_path, folder_id, file_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
            cursor.connection.commit()
            return cursor.rowcount
    
    def find_folder_by_id(self, folder_id: str, user_id: int) -> Optional[Message]:
        with self._get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM messages WHERE folder_id = ? AND user_id = ? AND msg_type = 'folder'
            ''', (folder_id, user_id))
            row = cursor.fetchone()
            return Message.from_row(row)
    
    def find_folder_files(self, folder_id: str, user_id: int) -> List[Dict[str, Any]]:
        with self._get_cursor() as cursor:
            cursor.execute('''
                SELECT id, filename, saved_name, file_size, relative_path 
                FROM messages 
                WHERE folder_id = ? AND user_id = ? AND msg_type = 'folder_file'
            ''', (folder_id, user_id))
            return [
                {
                    'id': row['id'],
                    'filename': row['filename'],
                    'file_size': row['file_size'],
                    'relative_path': row['relative_path'],
                    'saved_name': row['saved_name']
                }
                for row in cursor.fetchall()
            ]
    
    def find_folder_file(self, file_id: int, folder_id: str, user_id: int) -> Optional[Message]:
        with self._get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM messages 
                WHERE id = ? AND folder_id = ? AND user_id = ? AND msg_type = 'folder_file'
            ''', (file_id, folder_id, user_id))
            row = cursor.fetchone()
            return Message.from_row(row)
    
    def delete_message(self, msg_id: int, user_id: int) -> Optional[Message]:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM messages WHERE id = ? AND user_id = ?',
                (msg_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            message = Message.from_row(row)
            deleted_at = get_beijing_time()
            
            if message.msg_type == 'folder':
                cursor.execute(
                    "UPDATE messages SET is_deleted = 1, deleted_at = ? WHERE folder_id = ?",
                    (deleted_at, message.folder_id,)
                )
            
            cursor.execute(
                "UPDATE messages SET is_deleted = 1, deleted_at = ? WHERE id = ?",
                (deleted_at, msg_id,)
            )
            cursor.connection.commit()
            return message
    
    def soft_delete_message(self, msg_id: int, user_id: int) -> Optional[Message]:
        return self.delete_message(msg_id, user_id)
    
    def restore_message(self, msg_id: int, user_id: int) -> Optional[Message]:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM messages WHERE id = ? AND user_id = ? AND is_deleted = 1',
                (msg_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            message = Message.from_row(row)
            
            if message.msg_type == 'folder':
                cursor.execute(
                    "UPDATE messages SET is_deleted = 0, deleted_at = NULL WHERE folder_id = ?",
                    (message.folder_id,)
                )
            
            cursor.execute(
                "UPDATE messages SET is_deleted = 0, deleted_at = NULL WHERE id = ?",
                (msg_id,)
            )
            cursor.connection.commit()
            return message
    
    def permanent_delete_message(self, msg_id: int, user_id: int) -> Optional[Message]:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM messages WHERE id = ? AND user_id = ?',
                (msg_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            message = Message.from_row(row)
            
            if message.msg_type == 'folder':
                cursor.execute('DELETE FROM messages WHERE folder_id = ?', (message.folder_id,))
            
            cursor.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
            cursor.connection.commit()
            return message
    
    def find_deleted_messages(self, user_id: int) -> List[Message]:
        with self._get_cursor() as cursor:
            cursor.execute('''
                SELECT id, user_id, msg_type, content, filename, saved_name, file_size, relative_path, 
                       folder_id, file_count, category_id, is_deleted, created_at, deleted_at
                FROM messages 
                WHERE user_id = ? AND is_deleted = 1 AND msg_type != 'folder_file'
                ORDER BY deleted_at DESC
            ''', (user_id,))
            return [Message.from_row(row) for row in cursor.fetchall()]
    
    def empty_trash(self, user_id: int) -> int:
        with self._get_cursor() as cursor:
            cursor.execute('''
                SELECT folder_id FROM messages 
                WHERE user_id = ? AND is_deleted = 1 AND msg_type = 'folder'
            ''', (user_id,))
            folder_ids = [row['folder_id'] for row in cursor.fetchall()]
            
            for folder_id in folder_ids:
                cursor.execute('DELETE FROM messages WHERE folder_id = ?', (folder_id,))
            
            cursor.execute('DELETE FROM messages WHERE user_id = ? AND is_deleted = 1', (user_id,))
            deleted_count = cursor.rowcount
            cursor.connection.commit()
            return deleted_count
