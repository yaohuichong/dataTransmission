# -*- coding: utf-8 -*-
import mimetypes
from flask import Blueprint, request, jsonify, session, Response, send_file, stream_with_context
from urllib.parse import quote
from ..services import MessageService, FileService
from .auth_controller import login_required


message_bp = Blueprint('message', __name__)
message_service = MessageService()
file_service = None


def init_file_service(upload_folder: str):
    global file_service
    file_service = FileService(upload_folder)


@message_bp.route('/api/messages', methods=['GET'])
@login_required
def get_messages():
    user_id = session['user_id']
    since = request.args.get('since', '0')
    category_id = request.args.get('category_id')
    
    if category_id:
        category_id = int(category_id) if category_id.isdigit() else None
    
    messages = message_service.get_messages(user_id, since, category_id)
    return jsonify({'messages': messages}), 200


@message_bp.route('/api/messages/search', methods=['GET'])
@login_required
def search_messages():
    user_id = session['user_id']
    
    keyword = request.args.get('keyword', '').strip()
    category_name = request.args.get('category_name', '').strip()
    file_type = request.args.get('file_type', '').strip()
    date = request.args.get('date', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    messages = message_service.search_messages(
        user_id=user_id,
        keyword=keyword,
        category_name=category_name,
        file_type=file_type,
        date=date,
        start_date=start_date,
        end_date=end_date
    )
    
    return jsonify({'messages': messages}), 200


@message_bp.route('/api/messages/text', methods=['POST'])
@login_required
def send_text():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    content = data.get('content', '')
    category_id = data.get('category_id')
    
    user_id = session['user_id']
    
    success, message, msg = message_service.send_text(
        user_id, content, category_id
    )
    
    if success:
        return jsonify({'message': message, 'msg': msg}), 201
    else:
        return jsonify({'error': message}), 400


@message_bp.route('/api/messages/file', methods=['POST'])
@login_required
def send_file():
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
    original_filename = file.filename
    relative_path = request.form.get('relative_path', '')
    category_id = request.form.get('category_id') or None
    
    user_id = session['user_id']
    
    success, message, msg = file_service.save_file(
        user_id=user_id,
        file_obj=file,
        original_filename=original_filename,
        relative_path=relative_path,
        category_id=category_id
    )
    
    if success:
        return jsonify({'message': message, 'msg': msg}), 201
    else:
        return jsonify({'error': message}), 500


@message_bp.route('/api/messages/folder', methods=['POST'])
@login_required
def send_folder():
    if 'files[]' not in request.files:
        return jsonify({'error': '未选择文件夹'}), 400
    
    files = request.files.getlist('files[]')
    
    if not files or len(files) == 0:
        return jsonify({'error': '未选择文件夹'}), 400
    
    user_id = session['user_id']
    
    folder_name = request.form.get('folder_name', 'folder')
    category_id = request.form.get('category_id') or None
    
    success, message, msg = file_service.save_folder(
        user_id=user_id,
        files=files,
        folder_name=folder_name,
        category_id=category_id
    )
    
    if success:
        return jsonify({'message': message, 'msg': msg}), 201
    else:
        return jsonify({'error': message}), 500


@message_bp.route('/api/messages/file/<int:msg_id>', methods=['GET'])
@login_required
def download_file(msg_id):
    user_id = session['user_id']
    
    filename, file_path, stream = file_service.get_file_stream(user_id, msg_id)
    
    if not filename:
        return jsonify({'error': '文件不存在或无权访问'}), 404
    
    preview = request.args.get('preview', 'false').lower() == 'true'
    
    mimetype, _ = mimetypes.guess_type(filename)
    if mimetype is None:
        mimetype = 'application/octet-stream'
    
    encoded_filename = quote(filename)
    
    return Response(
        stream_with_context(stream),
        mimetype=mimetype,
        headers={
            'Content-Disposition': f"{'inline' if preview else 'attachment'}; filename*=UTF-8''{encoded_filename}"
        }
    )


@message_bp.route('/api/messages/folder/<folder_id>', methods=['GET'])
@login_required
def download_folder(folder_id):
    user_id = session['user_id']
    
    download_format = request.args.get('format', 'zip')
    
    folder_name, format_type, stream = file_service.get_folder_stream(
        user_id, folder_id, download_format
    )
    
    if not folder_name:
        return jsonify({'error': '文件夹不存在或无权访问'}), 404
    
    encoded_filename = quote(folder_name)
    
    if format_type == 'tar':
        mimetype = 'application/x-tar'
        extension = '.tar'
    else:
        mimetype = 'application/zip'
        extension = '.zip'
    
    return Response(
        stream_with_context(stream),
        mimetype=mimetype,
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}{extension}"
        }
    )


@message_bp.route('/api/messages/folder/<folder_id>/files', methods=['GET'])
@login_required
def get_folder_files(folder_id):
    user_id = session['user_id']
    
    files = file_service.get_folder_files(user_id, folder_id)
    
    if files is None:
        return jsonify({'error': '文件夹不存在或无权访问'}), 404
    
    return jsonify({'files': files}), 200


@message_bp.route('/api/messages/folder/<folder_id>/file/<int:file_id>', methods=['GET'])
@login_required
def download_folder_file(folder_id, file_id):
    user_id = session['user_id']
    
    message, file_path = file_service.get_folder_file(user_id, folder_id, file_id)
    
    if not message:
        return jsonify({'error': '文件不存在或无权访问'}), 404
    
    mimetype, _ = mimetypes.guess_type(message.filename)
    if mimetype is None:
        mimetype = 'application/octet-stream'
    
    encoded_filename = quote(message.filename)
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=message.filename,
        mimetype=mimetype
    )


@message_bp.route('/api/messages/<int:msg_id>', methods=['DELETE'])
@login_required
def delete_message(msg_id):
    user_id = session['user_id']
    
    success, message = file_service.delete_file(user_id, msg_id)
    
    if success:
        return jsonify({'message': message}), 200
    else:
        return jsonify({'error': message}), 400
