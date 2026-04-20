# -*- coding: utf-8 -*-
import mimetypes
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, JSONResponse
from urllib.parse import quote
from pydantic import BaseModel
from ..services import MessageService, FileService
from .auth_controller import login_required


message_router = APIRouter(tags=['messages'])
message_service = MessageService()
file_service = None


def init_file_service(upload_folder: str):
    global file_service
    file_service = FileService(upload_folder)


class TextMessageRequest(BaseModel):
    content: str
    category_id: Optional[int] = None


@message_router.get('/api/messages')
async def get_messages(
    request: Request,
    since: str = '0',
    category_id: Optional[str] = None,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    cat_id = None
    if category_id and category_id.isdigit():
        cat_id = int(category_id)
    
    messages = message_service.get_messages(user_id, since, cat_id)
    return {'messages': messages}


@message_router.get('/api/messages/search')
async def search_messages(
    request: Request,
    keyword: str = '',
    category_name: str = '',
    file_type: str = '',
    date: str = '',
    start_date: str = '',
    end_date: str = '',
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    messages = message_service.search_messages(
        user_id=user_id,
        keyword=keyword.strip(),
        category_name=category_name.strip(),
        file_type=file_type.strip(),
        date=date,
        start_date=start_date,
        end_date=end_date
    )
    
    return {'messages': messages}


@message_router.post('/api/messages/text')
async def send_text(
    request: Request,
    data: TextMessageRequest,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message, msg = message_service.send_text(
        user_id, data.content, data.category_id
    )
    
    if success:
        return {'message': message, 'msg': msg}
    else:
        raise HTTPException(status_code=400, detail=message)


@message_router.post('/api/messages/file')
async def send_file(
    request: Request,
    file: UploadFile = File(...),
    relative_path: str = Form(''),
    category_id: Optional[str] = Form(None),
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    if not file.filename:
        raise HTTPException(status_code=400, detail='未选择文件')
    
    cat_id = int(category_id) if category_id and category_id.isdigit() else None
    
    success, message, msg = await file_service.save_file_async(
        user_id=user_id,
        file_obj=file,
        original_filename=file.filename,
        relative_path=relative_path,
        category_id=cat_id
    )
    
    if success:
        return JSONResponse(status_code=201, content={'message': message, 'msg': msg})
    else:
        raise HTTPException(status_code=500, detail=message)


@message_router.post('/api/messages/folder')
async def send_folder(
    request: Request,
    files: List[UploadFile] = File(..., alias='files[]'),
    folder_name: str = Form('folder'),
    category_id: Optional[str] = Form(None),
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail='未选择文件夹')
    
    cat_id = int(category_id) if category_id and category_id.isdigit() else None
    
    success, message, msg = await file_service.save_folder_async(
        user_id=user_id,
        files=files,
        folder_name=folder_name,
        category_id=cat_id
    )
    
    if success:
        return JSONResponse(status_code=201, content={'message': message, 'msg': msg})
    else:
        raise HTTPException(status_code=500, detail=message)


@message_router.get('/api/messages/file/{msg_id}')
async def download_file(
    request: Request,
    msg_id: int,
    preview: str = 'false',
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    filename, file_path, stream = file_service.get_file_stream(user_id, msg_id)
    
    if not filename:
        raise HTTPException(status_code=404, detail='文件不存在或无权访问')
    
    is_preview = preview.lower() == 'true'
    
    mimetype, _ = mimetypes.guess_type(filename)
    if mimetype is None:
        mimetype = 'application/octet-stream'
    
    encoded_filename = quote(filename)
    
    return StreamingResponse(
        stream,
        media_type=mimetype,
        headers={
            'Content-Disposition': f"{'inline' if is_preview else 'attachment'}; filename*=UTF-8''{encoded_filename}"
        }
    )


@message_router.get('/api/messages/folder/{folder_id}')
async def download_folder(
    request: Request,
    folder_id: str,
    format: str = 'zip',
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    folder_name, format_type, stream = file_service.get_folder_stream(
        user_id, folder_id, format
    )
    
    if not folder_name:
        raise HTTPException(status_code=404, detail='文件夹不存在或无权访问')
    
    encoded_filename = quote(folder_name)
    
    if format_type == 'tar':
        mimetype = 'application/x-tar'
        extension = '.tar'
    else:
        mimetype = 'application/zip'
        extension = '.zip'
    
    return StreamingResponse(
        stream,
        media_type=mimetype,
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}{extension}"
        }
    )


@message_router.get('/api/messages/folder/{folder_id}/files')
async def get_folder_files(
    request: Request,
    folder_id: str,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    files = file_service.get_folder_files(user_id, folder_id)
    
    if files is None:
        raise HTTPException(status_code=404, detail='文件夹不存在或无权访问')
    
    return {'files': files}


@message_router.get('/api/messages/folder/{folder_id}/file/{file_id}')
async def download_folder_file(
    request: Request,
    folder_id: str,
    file_id: int,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    message, file_path = file_service.get_folder_file(user_id, folder_id, file_id)
    
    if not message:
        raise HTTPException(status_code=404, detail='文件不存在或无权访问')
    
    mimetype, _ = mimetypes.guess_type(message.filename)
    if mimetype is None:
        mimetype = 'application/octet-stream'
    
    encoded_filename = quote(message.filename)
    
    def iterfile():
        with open(file_path, 'rb') as f:
            while chunk := f.read(64 * 1024):
                yield chunk
    
    return StreamingResponse(
        iterfile(),
        media_type=mimetype,
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@message_router.delete('/api/messages/{msg_id}')
async def delete_message(
    request: Request,
    msg_id: int,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message = file_service.delete_file(user_id, msg_id)
    
    if success:
        return {'message': message}
    else:
        raise HTTPException(status_code=400, detail=message)


@message_router.get('/api/trash')
async def get_trash(
    request: Request,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    messages = file_service.get_trash(user_id)
    return {'messages': messages}


@message_router.post('/api/trash/{msg_id}/restore')
async def restore_message(
    request: Request,
    msg_id: int,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message = file_service.restore_message(user_id, msg_id)
    
    if success:
        return {'message': message}
    else:
        raise HTTPException(status_code=400, detail=message)


@message_router.delete('/api/trash/{msg_id}')
async def permanent_delete_message(
    request: Request,
    msg_id: int,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message = file_service.permanent_delete(user_id, msg_id)
    
    if success:
        return {'message': message}
    else:
        raise HTTPException(status_code=400, detail=message)


@message_router.delete('/api/trash')
async def empty_trash(
    request: Request,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message, count = file_service.empty_trash(user_id)
    
    if success:
        return {'message': message, 'count': count}
    else:
        raise HTTPException(status_code=400, detail=message)
