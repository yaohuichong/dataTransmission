# -*- coding: utf-8 -*-
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: Optional[int] = None
    username: str = ''
    password_hash: str = ''
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row) -> 'User':
        if row is None:
            return None
        return cls(
            id=row['id'],
            username=row['username'],
            password_hash=row['password_hash'],
            created_at=row['created_at']
        )


@dataclass
class Category:
    id: Optional[int] = None
    user_id: int = 0
    name: str = ''
    parent_id: Optional[int] = None
    created_at: Optional[datetime] = None
    is_deleted: int = 0
    deleted_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row) -> 'Category':
        if row is None:
            return None
        return cls(
            id=row['id'],
            user_id=row['user_id'],
            name=row['name'],
            parent_id=row['parent_id'],
            created_at=row['created_at'],
            is_deleted=row['is_deleted'] if 'is_deleted' in row.keys() else 0,
            deleted_at=row['deleted_at'] if 'deleted_at' in row.keys() else None
        )


@dataclass
class Message:
    id: Optional[int] = None
    user_id: int = 0
    msg_type: str = ''
    content: Optional[str] = None
    filename: Optional[str] = None
    saved_name: Optional[str] = None
    file_size: Optional[int] = None
    relative_path: Optional[str] = None
    folder_id: Optional[str] = None
    file_count: Optional[int] = None
    category_id: Optional[int] = None
    created_at: Optional[datetime] = None
    is_deleted: int = 0
    deleted_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row) -> 'Message':
        if row is None:
            return None
        return cls(
            id=row['id'],
            user_id=row['user_id'],
            msg_type=row['msg_type'],
            content=row['content'],
            filename=row['filename'],
            saved_name=row['saved_name'],
            file_size=row['file_size'],
            relative_path=row['relative_path'],
            folder_id=row['folder_id'],
            file_count=row['file_count'],
            category_id=row['category_id'],
            created_at=row['created_at'],
            is_deleted=row['is_deleted'] if 'is_deleted' in row.keys() else 0,
            deleted_at=row['deleted_at'] if 'deleted_at' in row.keys() else None
        )
    
    def to_dict(self) -> dict:
        result = {
            'id': self.id,
            'type': self.msg_type,
            'time': self.created_at,
            'category_id': self.category_id
        }
        if self.msg_type == 'text':
            result['content'] = self.content
        elif self.msg_type == 'folder':
            result['filename'] = self.filename
            result['file_size'] = self.file_size
            result['folder_id'] = self.folder_id
            result['file_count'] = self.file_count
        else:
            result['filename'] = self.filename
            result['file_size'] = self.file_size
            result['file_id'] = self.id
            result['relative_path'] = self.relative_path or ''
        return result
