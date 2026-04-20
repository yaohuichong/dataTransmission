# -*- coding: utf-8 -*-
import os
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Generator
from fastapi import UploadFile
from ..repositories import MessageRepository, MessageSearchParams
from ..models import Message
from ..utils import (
    get_user_upload_folder, 
    ensure_directory,
    stream_file,
    true_streaming_zip,
    stream_tar_directory
)


class FileService:
    def __init__(self, upload_folder: str, message_repo: MessageRepository = None):
        self._upload_folder = upload_folder
        self._message_repo = message_repo or MessageRepository()
    
    async def save_file_async(
        self, user_id: int, file_obj: UploadFile, original_filename: str,
        relative_path: str = '', category_id: int = None
    ) -> Tuple[bool, str, Optional[dict]]:
        user_folder = get_user_upload_folder(self._upload_folder, user_id)
        
        saved_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        if relative_path:
            dir_path = os.path.join(user_folder, os.path.dirname(relative_path))
            ensure_directory(dir_path)
            file_path = os.path.join(user_folder, relative_path)
            saved_name = relative_path
        else:
            file_path = os.path.join(user_folder, saved_name)
        
        try:
            with open(file_path, 'wb') as f:
                while chunk := await file_obj.read(1024 * 1024):
                    f.write(chunk)
            file_size = os.path.getsize(file_path)
            
            msg_id, created_at = self._message_repo.create_file_message(
                user_id=user_id,
                filename=original_filename,
                saved_name=saved_name,
                file_size=file_size,
                relative_path=relative_path,
                category_id=category_id
            )
            
            return True, '发送成功', {
                'id': msg_id,
                'type': 'file',
                'filename': original_filename,
                'file_size': file_size,
                'file_id': msg_id,
                'relative_path': relative_path,
                'time': created_at,
                'category_id': category_id
            }
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            return False, '发送失败', None
    
    async def save_folder_async(
        self, user_id: int, files: List[UploadFile], folder_name: str, category_id: int = None
    ) -> Tuple[bool, str, Optional[dict]]:
        user_folder = get_user_upload_folder(self._upload_folder, user_id)
        folder_id = uuid.uuid4().hex
        folder_path = os.path.join(user_folder, folder_id)
        ensure_directory(folder_path)
        
        total_size = 0
        file_count = 0
        file_records = []
        
        try:
            for file in files:
                if file.filename == '':
                    continue
                
                relative_path = file.filename
                file_path = os.path.join(folder_path, relative_path)
                
                dir_path = os.path.dirname(file_path)
                ensure_directory(dir_path)
                
                with open(file_path, 'wb') as f:
                    while chunk := await file.read(1024 * 1024):
                        f.write(chunk)
                file_size = os.path.getsize(file_path)
                total_size += file_size
                file_count += 1
                
                file_records.append({
                    'filename': os.path.basename(relative_path),
                    'saved_name': file_path,
                    'file_size': file_size,
                    'relative_path': relative_path
                })
            
            self._message_repo.batch_create_folder_files(
                user_id=user_id,
                folder_id=folder_id,
                files=file_records
            )
            
            msg_id, created_at = self._message_repo.create_folder_message(
                user_id=user_id,
                folder_name=folder_name,
                folder_path=folder_path,
                folder_id=folder_id,
                total_size=total_size,
                file_count=file_count,
                category_id=category_id
            )
            
            return True, '发送成功', {
                'id': msg_id,
                'type': 'folder',
                'filename': folder_name,
                'file_size': total_size,
                'file_count': file_count,
                'folder_id': folder_id,
                'time': created_at,
                'category_id': category_id
            }
        except Exception as e:
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
            return False, '发送失败', None
    
    def get_file_stream(self, user_id: int, msg_id: int) -> Tuple[Optional[str], Optional[str], Optional[Generator]]:
        message = self._message_repo.find_by_id(msg_id, user_id)
        
        if not message or message.msg_type != 'file':
            return None, None, None
        
        user_folder = get_user_upload_folder(self._upload_folder, user_id)
        file_path = os.path.join(user_folder, message.saved_name)
        
        if not os.path.exists(file_path):
            return None, None, None
        
        return message.filename, file_path, stream_file(file_path)
    
    def get_folder_stream(
        self, user_id: int, folder_id: str, format_type: str = 'zip'
    ) -> Tuple[Optional[str], Optional[str], Optional[Generator]]:
        message = self._message_repo.find_folder_by_id(folder_id, user_id)
        
        if not message:
            return None, None, None
        
        folder_path = message.saved_name
        folder_name = message.filename
        
        if not os.path.exists(folder_path):
            return None, None, None
        
        if format_type == 'tar':
            return folder_name, 'tar', stream_tar_directory(folder_path)
        else:
            return folder_name, 'zip', true_streaming_zip(folder_path)
    
    def get_folder_files(self, user_id: int, folder_id: str) -> Optional[List[dict]]:
        return self._message_repo.find_folder_files(folder_id, user_id)
    
    def get_folder_file(self, user_id: int, folder_id: str, file_id: int) -> Tuple[Optional[Message], Optional[str]]:
        message = self._message_repo.find_folder_file(file_id, folder_id, user_id)
        
        if not message:
            return None, None
        
        file_path = message.saved_name
        
        if not os.path.exists(file_path):
            return None, None
        
        return message, file_path
    
    def delete_file(self, user_id: int, msg_id: int, permanent: bool = False) -> Tuple[bool, str]:
        if permanent:
            message = self._message_repo.permanent_delete_message(msg_id, user_id)
            if not message:
                return False, '消息不存在或无权删除'
            
            if message.msg_type == 'file':
                user_folder = get_user_upload_folder(self._upload_folder, user_id)
                file_path = os.path.join(user_folder, message.saved_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            elif message.msg_type == 'folder':
                folder_path = message.saved_name
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
            
            return True, '已彻底删除'
        
        message = self._message_repo.soft_delete_message(msg_id, user_id)
        
        if not message:
            return False, '消息不存在或无权删除'
        
        return True, '已移至回收站'
    
    def get_trash(self, user_id: int) -> List[dict]:
        messages = self._message_repo.find_deleted_messages(user_id)
        result = []
        for m in messages:
            item = m.to_dict()
            item['deleted_at'] = m.deleted_at
            result.append(item)
        return result
    
    def restore_message(self, user_id: int, msg_id: int) -> Tuple[bool, str]:
        message = self._message_repo.restore_message(msg_id, user_id)
        if not message:
            return False, '消息不存在或无法恢复'
        return True, '恢复成功'
    
    def permanent_delete(self, user_id: int, msg_id: int) -> Tuple[bool, str]:
        return self.delete_file(user_id, msg_id, permanent=True)
    
    def empty_trash(self, user_id: int) -> Tuple[bool, str, int]:
        messages = self._message_repo.find_deleted_messages(user_id)
        
        for m in messages:
            if m.msg_type == 'file':
                user_folder = get_user_upload_folder(self._upload_folder, user_id)
                file_path = os.path.join(user_folder, m.saved_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            elif m.msg_type == 'folder':
                folder_path = m.saved_name
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
        
        deleted_count = self._message_repo.empty_trash(user_id)
        return True, f'已清空回收站，共删除 {deleted_count} 条记录', deleted_count


class MessageService:
    def __init__(self, message_repo: MessageRepository = None):
        self._message_repo = message_repo or MessageRepository()
    
    def get_messages(
        self, user_id: int, since: str = '0', category_id: int = None
    ) -> List[dict]:
        messages = self._message_repo.find_messages(user_id, since, category_id)
        return [m.to_dict() for m in messages]
    
    def search_messages(
        self, user_id: int, keyword: str = '', category_name: str = '',
        file_type: str = '', date: str = '', start_date: str = '', end_date: str = ''
    ) -> List[dict]:
        params = MessageSearchParams(
            user_id=user_id,
            keyword=keyword,
            category_name=category_name,
            file_type=file_type,
            date=date,
            start_date=start_date,
            end_date=end_date
        )
        return self._message_repo.search(params)
    
    def send_text(
        self, user_id: int, content: str, category_id: int = None
    ) -> Tuple[bool, str, Optional[dict]]:
        content = content.strip() if content else ''
        
        if not content:
            return False, '消息内容不能为空', None
        
        if len(content) > 500000:
            return False, '消息内容过长，最大支持50万字符', None
        
        try:
            msg_id, created_at = self._message_repo.create_text_message(
                user_id=user_id,
                content=content,
                category_id=category_id
            )
            
            return True, '发送成功', {
                'id': msg_id,
                'type': 'text',
                'content': content,
                'time': created_at,
                'category_id': category_id
            }
        except Exception:
            return False, '发送失败', None
