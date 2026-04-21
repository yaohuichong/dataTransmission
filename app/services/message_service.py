# -*- coding: utf-8 -*-
import os
import uuid
import shutil
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Generator, Set
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

logger = logging.getLogger(__name__)

FILE_SIGNATURES: Dict[str, bytes] = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'BM': 'image/bmp',
    b'RIFF': 'video/avi',
    b'\x00\x00\x01\x00': 'image/x-icon',
    b'%PDF': 'application/pdf',
    b'PK\x03\x04': 'application/zip',
    b'Rar!': 'application/x-rar-compressed',
    b'\x1f\x8b': 'application/gzip',
    b'BZh': 'application/x-bzip2',
    b'\xfd7zXZ\x00': 'application/x-xz',
}


class FileService:
    def __init__(
        self, 
        upload_folder: str, 
        message_repo: MessageRepository = None,
        max_file_size: int = 50 * 1024 * 1024,
        blocked_extensions: Set[str] = None,
        allowed_mime_types: Set[str] = None,
        ws_manager = None
    ):
        self._upload_folder = upload_folder
        self._message_repo = message_repo or MessageRepository()
        self._max_file_size = max_file_size
        self._blocked_extensions = blocked_extensions or set()
        self._allowed_mime_types = allowed_mime_types
        self._ws_manager = ws_manager
    
    def set_ws_manager(self, ws_manager):
        self._ws_manager = ws_manager
    
    def _get_file_extension(self, filename: str) -> str:
        return os.path.splitext(filename)[1].lower()
    
    def _validate_extension(self, filename: str) -> Tuple[bool, str]:
        ext = self._get_file_extension(filename)
        
        if not ext:
            return True, ''
        
        if ext in self._blocked_extensions:
            return False, f'不允许上传 {ext} 类型的文件'
        
        return True, ''
    
    def _detect_mime_by_signature(self, file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
            
            for signature, mime_type in FILE_SIGNATURES.items():
                if header.startswith(signature):
                    return mime_type
        except Exception as e:
            logger.warning(f"Failed to detect MIME type: {e}")
        return None
    
    def _sanitize_path(self, base_path: str, target_path: str) -> str:
        real_base = os.path.realpath(base_path)
        real_target = os.path.realpath(target_path)
        
        if not real_target.startswith(real_base):
            raise ValueError("Path traversal detected")
        
        return real_target
    
    def _validate_file_size(self, file_size: int) -> Tuple[bool, str]:
        if self._max_file_size > 0 and file_size > self._max_file_size:
            max_mb = self._max_file_size / (1024 * 1024)
            return False, f'文件大小超过限制，最大允许 {max_mb:.0f}MB'
        return True, ''
    
    async def save_file_async(
        self, user_id: int, file_obj: UploadFile, original_filename: str,
        relative_path: str = '', category_id: int = None
    ) -> Tuple[bool, str, Optional[dict]]:
        if not original_filename:
            return False, '文件名不能为空', None
        
        original_filename = os.path.basename(original_filename)
        
        valid, msg = self._validate_extension(original_filename)
        if not valid:
            return False, msg, None
        
        user_folder = get_user_upload_folder(self._upload_folder, user_id)
        
        saved_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            if relative_path:
                relative_path = relative_path.replace('..', '').lstrip('/\\')
                dir_path = os.path.join(user_folder, os.path.dirname(relative_path))
                ensure_directory(dir_path)
                file_path = os.path.join(user_folder, relative_path)
                saved_name = relative_path
            else:
                file_path = os.path.join(user_folder, saved_name)
            
            try:
                file_path = self._sanitize_path(user_folder, file_path)
            except ValueError:
                return False, '非法的文件路径', None
            
            file_size = 0
            with open(file_path, 'wb') as f:
                while chunk := await file_obj.read(1024 * 1024):
                    file_size += len(chunk)
                    
                    valid, msg = self._validate_file_size(file_size)
                    if not valid:
                        f.close()
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        return False, msg, None
                    
                    f.write(chunk)
            
            if file_size == 0:
                if os.path.exists(file_path):
                    os.remove(file_path)
                return False, '文件内容为空', None
            
            msg_id, created_at = self._message_repo.create_file_message(
                user_id=user_id,
                filename=original_filename,
                saved_name=saved_name,
                file_size=file_size,
                relative_path=relative_path,
                category_id=category_id
            )
            
            msg_data = {
                'id': msg_id,
                'type': 'file',
                'filename': original_filename,
                'file_size': file_size,
                'file_id': msg_id,
                'relative_path': relative_path,
                'time': created_at,
                'category_id': category_id
            }
            
            if self._ws_manager:
                await self._ws_manager.broadcast_new_message(user_id, msg_data)
            
            return True, '发送成功', msg_data
        except Exception as e:
            logger.error(f"File upload error: {e}")
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
                
                filename = os.path.basename(file.filename)
                valid, msg = self._validate_extension(filename)
                if not valid:
                    continue
                
                relative_path = file.filename.replace('..', '').lstrip('/\\')
                file_path = os.path.join(folder_path, relative_path)
                
                try:
                    file_path = self._sanitize_path(folder_path, file_path)
                except ValueError:
                    logger.warning(f"Path traversal attempt in folder upload: {relative_path}")
                    continue
                
                dir_path = os.path.dirname(file_path)
                ensure_directory(dir_path)
                
                file_size = 0
                with open(file_path, 'wb') as f:
                    while chunk := await file.read(1024 * 1024):
                        file_size += len(chunk)
                        total_size += len(chunk)
                        
                        if self._max_file_size > 0 and total_size > self._max_file_size:
                            f.close()
                            shutil.rmtree(folder_path)
                            return False, '文件夹总大小超过限制', None
                        
                        f.write(chunk)
                
                if file_size == 0:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    continue
                
                file_count += 1
                
                file_records.append({
                    'filename': os.path.basename(relative_path),
                    'saved_name': file_path,
                    'file_size': file_size,
                    'relative_path': relative_path
                })
            
            if file_count == 0:
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
                return False, '文件夹为空或不包含有效文件', None
            
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
            
            msg_data = {
                'id': msg_id,
                'type': 'folder',
                'filename': folder_name,
                'file_size': total_size,
                'file_count': file_count,
                'folder_id': folder_id,
                'time': created_at,
                'category_id': category_id
            }
            
            if self._ws_manager:
                await self._ws_manager.broadcast_new_message(user_id, msg_data)
            
            return True, '发送成功', msg_data
        except Exception as e:
            logger.error(f"Folder upload error: {e}")
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
    def __init__(self, message_repo: MessageRepository = None, ws_manager=None):
        self._message_repo = message_repo or MessageRepository()
        self._ws_manager = ws_manager
    
    def set_ws_manager(self, ws_manager):
        self._ws_manager = ws_manager
    
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
    
    async def send_text_async(
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
            
            msg_data = {
                'id': msg_id,
                'type': 'text',
                'content': content,
                'time': created_at,
                'category_id': category_id
            }
            
            if self._ws_manager:
                await self._ws_manager.broadcast_new_message(user_id, msg_data)
            
            return True, '发送成功', msg_data
        except Exception:
            return False, '发送失败', None
