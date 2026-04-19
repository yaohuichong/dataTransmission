# -*- coding: utf-8 -*-
import os
import uuid
import sqlite3
import zipfile
import io
from datetime import datetime
from functools import wraps
from urllib.parse import quote
from flask import Flask, request, jsonify, session, send_file, render_template, redirect, url_for, Response, stream_with_context, g
import bcrypt

app = Flask(__name__)
app.secret_key = 'file-transfer-helper-secret-key-2024'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.sqlite')

FILE_TYPE_EXTENSIONS = {
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'},
    'document': {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.rtf', '.odt', '.ods', '.odp'},
    'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp'},
    'audio': {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma', '.ape', '.aiff'},
    'archive': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz'}
}

ALL_KNOWN_EXTENSIONS = set()
for exts in FILE_TYPE_EXTENSIONS.values():
    ALL_KNOWN_EXTENSIONS.update(exts)

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    for ftype, extensions in FILE_TYPE_EXTENSIONS.items():
        if ext in extensions:
            return ftype
    return 'other'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
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
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_messages_category 
        ON messages(user_id, category_id)
    ''')
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_user_upload_folder(user_id):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], f'user_{user_id}')
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', username=session.get('username'))

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    if len(username) < 3 or len(username) > 50:
        return jsonify({'error': '用户名长度需要在3-50个字符之间'}), 400
    
    if len(password) < 6:
        return jsonify({'error': '密码长度至少需要6个字符'}), 400
    
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        return jsonify({'message': '注册成功，请登录'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': '用户名已存在'}), 400
    except Exception as e:
        return jsonify({'error': '注册失败，请稍后重试'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    if not user:
        return jsonify({'error': '用户名或密码错误'}), 401
    
    if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return jsonify({'error': '用户名或密码错误'}), 401
    
    session['user_id'] = user['id']
    session['username'] = user['username']
    
    return jsonify({'message': '登录成功', 'username': user['username']}), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': '已退出登录'}), 200

@app.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, parent_id 
        FROM categories 
        WHERE user_id = ?
        ORDER BY created_at ASC
    ''', (user_id,))
    categories = cursor.fetchall()
    
    return jsonify({
        'categories': [{'id': c['id'], 'name': c['name'], 'parent_id': c['parent_id']} for c in categories]
    }), 200

@app.route('/api/categories', methods=['POST'])
@login_required
def create_category():
    user_id = session['user_id']
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    name = data.get('name', '').strip()
    parent_id = data.get('parent_id')
    
    if not name:
        return jsonify({'error': '目录名称不能为空'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO categories (user_id, name, parent_id)
        VALUES (?, ?, ?)
    ''', (user_id, name, parent_id))
    conn.commit()
    category_id = cursor.lastrowid
    
    return jsonify({
        'message': '创建成功',
        'category': {'id': category_id, 'name': name, 'parent_id': parent_id}
    }), 201

@app.route('/api/categories/<int:category_id>', methods=['PUT'])
@login_required
def update_category(category_id):
    user_id = session['user_id']
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': '目录名称不能为空'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM categories WHERE id = ? AND user_id = ?', (category_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': '目录不存在'}), 404
    
    cursor.execute('UPDATE categories SET name = ? WHERE id = ?', (name, category_id))
    conn.commit()
    
    return jsonify({'message': '更新成功'}), 200

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
@login_required
def delete_category(category_id):
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM categories WHERE id = ? AND user_id = ?', (category_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': '目录不存在'}), 404
    
    cursor.execute('UPDATE messages SET category_id = NULL WHERE category_id = ?', (category_id,))
    cursor.execute('UPDATE categories SET parent_id = NULL WHERE parent_id = ?', (category_id,))
    cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
    conn.commit()
    
    return jsonify({'message': '删除成功'}), 200

@app.route('/api/messages', methods=['GET'])
@login_required
def get_messages():
    user_id = session['user_id']
    since = request.args.get('since', '0')
    category_id = request.args.get('category_id', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = '''
        SELECT id, msg_type, content, filename, file_size, relative_path, folder_id, file_count, category_id,
               datetime(created_at, '+8 hours') as created_at
        FROM messages 
        WHERE user_id = ? AND id > ? AND msg_type != 'folder_file'
    '''
    params = [user_id, since]
    
    if category_id:
        query += ' AND category_id = ?'
        params.append(category_id)
    
    query += ' ORDER BY created_at ASC'
    
    cursor.execute(query, params)
    messages = cursor.fetchall()
    
    msg_list = []
    for m in messages:
        msg = {
            'id': m['id'],
            'type': m['msg_type'],
            'time': m['created_at'],
            'category_id': m['category_id']
        }
        if m['msg_type'] == 'text':
            msg['content'] = m['content']
        elif m['msg_type'] == 'folder':
            msg['filename'] = m['filename']
            msg['file_size'] = m['file_size']
            msg['folder_id'] = m['folder_id']
            msg['file_count'] = m['file_count']
        else:
            msg['filename'] = m['filename']
            msg['file_size'] = m['file_size']
            msg['file_id'] = m['id']
            msg['relative_path'] = m['relative_path'] or ''
        msg_list.append(msg)
    
    return jsonify({'messages': msg_list}), 200

@app.route('/api/messages/search', methods=['GET'])
@login_required
def search_messages():
    user_id = session['user_id']
    keyword = request.args.get('keyword', '').strip()
    category_name = request.args.get('category_name', '').strip()
    file_type = request.args.get('file_type', '').strip()
    date = request.args.get('date', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = '''SELECT m.id, m.msg_type, m.content, m.filename, m.file_size, m.relative_path, m.folder_id, m.file_count, m.category_id, 
               datetime(m.created_at, '+8 hours') as created_at, c.name as category_name
               FROM messages m 
               LEFT JOIN categories c ON m.category_id = c.id
               WHERE m.user_id = ? AND m.msg_type != 'folder_file' '''
    params = [user_id]
    
    if keyword:
        query += ' AND (m.content LIKE ? OR m.filename LIKE ? OR m.relative_path LIKE ?) '
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    
    if category_name:
        category_names = [name.strip() for name in category_name.split(',') if name.strip()]
        if len(category_names) == 1:
            query += ' AND c.name LIKE ? '
            params.append(f'%{category_names[0]}%')
        elif len(category_names) > 1:
            placeholders = ' OR '.join(['c.name LIKE ?' for _ in category_names])
            query += f' AND ({placeholders}) '
            params.extend([f'%{name}%' for name in category_names])
    
    if file_type:
        if file_type == 'text':
            query += " AND m.msg_type = 'text' "
        elif file_type == 'folder':
            query += " AND m.msg_type = 'folder' "
        elif file_type in FILE_TYPE_EXTENSIONS:
            extensions = FILE_TYPE_EXTENSIONS[file_type]
            placeholders = ' OR '.join([f"m.filename LIKE ?" for _ in extensions])
            query += f" AND m.msg_type = 'file' AND ({placeholders}) "
            params.extend([f'%{ext}' for ext in extensions])
        elif file_type == 'other':
            placeholders = ' OR '.join([f"m.filename LIKE ?" for _ in ALL_KNOWN_EXTENSIONS])
            query += f" AND m.msg_type = 'file' AND NOT ({placeholders}) "
            params.extend([f'%{ext}' for ext in ALL_KNOWN_EXTENSIONS])
    
    if date:
        query += ' AND DATE(m.created_at) = ? '
        params.append(date)
    
    if start_date:
        query += ' AND DATE(m.created_at) >= ? '
        params.append(start_date)
    
    if end_date:
        query += ' AND DATE(m.created_at) <= ? '
        params.append(end_date)
    
    query += ' ORDER BY m.created_at DESC LIMIT 100 '
    
    cursor.execute(query, params)
    messages = cursor.fetchall()
    
    msg_list = []
    for m in messages:
        msg = {
            'id': m['id'],
            'type': m['msg_type'],
            'time': m['created_at'],
            'category_id': m['category_id'],
            'category_name': m['category_name'] or ''
        }
        if m['msg_type'] == 'text':
            msg['content'] = m['content']
        elif m['msg_type'] == 'folder':
            msg['filename'] = m['filename']
            msg['file_size'] = m['file_size']
            msg['folder_id'] = m['folder_id']
            msg['file_count'] = m['file_count']
        else:
            msg['filename'] = m['filename']
            msg['file_size'] = m['file_size']
            msg['file_id'] = m['id']
            msg['relative_path'] = m['relative_path'] or ''
        msg_list.append(msg)
    
    return jsonify({'messages': msg_list}), 200

@app.route('/api/messages/text', methods=['POST'])
@login_required
def send_text():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': '消息内容不能为空'}), 400
    
    if len(content) > 500000:
        return jsonify({'error': '消息内容过长，最大支持50万字符'}), 400
    
    user_id = session['user_id']
    category_id = data.get('category_id')
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (user_id, msg_type, content, category_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'text', content, category_id))
        conn.commit()
        msg_id = cursor.lastrowid
        cursor.execute('SELECT datetime(created_at, \'+8 hours\') as created_at FROM messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        
        return jsonify({
            'message': '发送成功',
            'msg': {
                'id': msg_id,
                'type': 'text',
                'content': content,
                'time': row['created_at'],
                'category_id': category_id
            }
        }), 201
    except Exception as e:
        return jsonify({'error': '发送失败'}), 500

@app.route('/api/messages/file', methods=['POST'])
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
    
    saved_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    user_id = session['user_id']
    user_folder = get_user_upload_folder(user_id)
    
    if relative_path:
        dir_path = os.path.join(user_folder, os.path.dirname(relative_path))
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        file_path = os.path.join(user_folder, relative_path)
    else:
        file_path = os.path.join(user_folder, saved_name)
    
    file.save(file_path)
    file_size = os.path.getsize(file_path)
    
    if relative_path:
        saved_name = relative_path
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (user_id, msg_type, filename, saved_name, file_size, relative_path, category_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, 'file', original_filename, saved_name, file_size, relative_path, category_id))
        conn.commit()
        msg_id = cursor.lastrowid
        cursor.execute('SELECT datetime(created_at, \'+8 hours\') as created_at FROM messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        
        return jsonify({
            'message': '发送成功',
            'msg': {
                'id': msg_id,
                'type': 'file',
                'filename': original_filename,
                'file_size': file_size,
                'file_id': msg_id,
                'relative_path': relative_path,
                'time': row['created_at'],
                'category_id': category_id
            }
        }), 201
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'error': '发送失败'}), 500

@app.route('/api/messages/folder', methods=['POST'])
@login_required
def send_folder():
    if 'files[]' not in request.files:
        return jsonify({'error': '未选择文件夹'}), 400
    
    files = request.files.getlist('files[]')
    
    if not files or len(files) == 0:
        return jsonify({'error': '未选择文件夹'}), 400
    
    user_id = session['user_id']
    user_folder = get_user_upload_folder(user_id)
    
    folder_name = request.form.get('folder_name', 'folder')
    category_id = request.form.get('category_id') or None
    folder_id = uuid.uuid4().hex
    
    folder_path = os.path.join(user_folder, folder_id)
    os.makedirs(folder_path, exist_ok=True)
    
    total_size = 0
    file_count = 0
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        for file in files:
            if file.filename == '':
                continue
            
            relative_path = file.filename
            file_path = os.path.join(folder_path, relative_path)
            
            dir_path = os.path.dirname(file_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            
            file.save(file_path)
            total_size += os.path.getsize(file_path)
            file_count += 1
            
            cursor.execute('''
                INSERT INTO messages (user_id, msg_type, filename, saved_name, file_size, relative_path, folder_id, file_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 'folder_file', os.path.basename(relative_path), file_path, os.path.getsize(file_path), relative_path, folder_id, len(files)))
        
        cursor.execute('''
            INSERT INTO messages (user_id, msg_type, filename, saved_name, file_size, folder_id, file_count, category_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, 'folder', folder_name, folder_path, total_size, folder_id, file_count, category_id))
        
        msg_id = cursor.lastrowid
        cursor.execute('SELECT datetime(created_at, \'+8 hours\') as created_at FROM messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        conn.commit()
        
        return jsonify({
            'message': '发送成功',
            'msg': {
                'id': msg_id,
                'type': 'folder',
                'filename': folder_name,
                'file_size': total_size,
                'file_count': file_count,
                'folder_id': folder_id,
                'time': row['created_at'],
                'category_id': category_id
            }
        }), 201
    except Exception as e:
        import shutil
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        return jsonify({'error': '发送失败'}), 500

@app.route('/api/messages/folder/<folder_id>', methods=['GET'])
@login_required
def download_folder(folder_id):
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM messages WHERE folder_id = ? AND user_id = ? AND msg_type = 'folder'
    ''', (folder_id, user_id))
    record = cursor.fetchone()
    
    if not record:
        return jsonify({'error': '文件夹不存在或无权访问'}), 404
    
    folder_path = record['saved_name']
    folder_name = record['filename']
    
    if not os.path.exists(folder_path):
        return jsonify({'error': '文件夹不存在'}), 404
    
    download_format = request.args.get('format', 'zip')
    encoded_filename = quote(folder_name)
    
    def generate_zip():
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path)
                    zf.write(file_path, arcname)
        zip_buffer.seek(0)
        while True:
            chunk = zip_buffer.read(8192)
            if not chunk:
                break
            yield chunk
    
    def generate_tar():
        import tarfile
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w') as tf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path)
                    tf.add(file_path, arcname)
        tar_buffer.seek(0)
        while True:
            chunk = tar_buffer.read(8192)
            if not chunk:
                break
            yield chunk
    
    if download_format == 'tar':
        return Response(
            stream_with_context(generate_tar()),
            mimetype='application/x-tar',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}.tar"
            }
        )
    else:
        return Response(
            stream_with_context(generate_zip()),
            mimetype='application/zip',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}.zip"
            }
        )

@app.route('/api/messages/folder/<folder_id>/files', methods=['GET'])
@login_required
def get_folder_files(folder_id):
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, filename, saved_name, file_size, relative_path FROM messages 
        WHERE folder_id = ? AND user_id = ? AND msg_type = 'folder_file'
    ''', (folder_id, user_id))
    records = cursor.fetchall()
    
    files = []
    for record in records:
        files.append({
            'id': record['id'],
            'filename': record['filename'],
            'file_size': record['file_size'],
            'relative_path': record['relative_path'],
            'saved_name': record['saved_name']
        })
    
    return jsonify({'files': files})

@app.route('/api/messages/folder/<folder_id>/file/<int:file_id>', methods=['GET'])
@login_required
def download_folder_file(folder_id, file_id):
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM messages WHERE id = ? AND folder_id = ? AND user_id = ? AND msg_type = 'folder_file'
    ''', (file_id, folder_id, user_id))
    record = cursor.fetchone()
    
    if not record:
        return jsonify({'error': '文件不存在或无权访问'}), 404
    
    file_path = record['saved_name']
    
    if not os.path.exists(file_path):
        return jsonify({'error': '文件不存在'}), 404
    
    from flask import send_file
    import mimetypes
    
    mimetype, _ = mimetypes.guess_type(record['filename'])
    if mimetype is None:
        mimetype = 'application/octet-stream'
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=record['filename'],
        mimetype=mimetype
    )

@app.route('/api/messages/file/<int:msg_id>', methods=['GET'])
@login_required
def download_file(msg_id):
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM messages WHERE id = ? AND user_id = ? AND msg_type = 'file'
    ''', (msg_id, user_id))
    record = cursor.fetchone()
    
    if not record:
        return jsonify({'error': '文件不存在或无权访问'}), 404
    
    user_folder = get_user_upload_folder(user_id)
    file_path = os.path.join(user_folder, record['saved_name'])
    
    if not os.path.exists(file_path):
        return jsonify({'error': '文件不存在'}), 404
    
    from flask import send_file
    import mimetypes
    
    preview = request.args.get('preview', 'false').lower() == 'true'
    
    mimetype, _ = mimetypes.guess_type(record['filename'])
    if mimetype is None:
        mimetype = 'application/octet-stream'
    
    return send_file(
        file_path,
        as_attachment=not preview,
        download_name=record['filename'],
        mimetype=mimetype
    )

@app.route('/api/messages/<int:msg_id>', methods=['DELETE'])
@login_required
def delete_message(msg_id):
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM messages WHERE id = ? AND user_id = ?
    ''', (msg_id, user_id))
    record = cursor.fetchone()
    
    if not record:
        return jsonify({'error': '消息不存在或无权删除'}), 404
    
    if record['msg_type'] == 'file':
        user_folder = get_user_upload_folder(user_id)
        file_path = os.path.join(user_folder, record['saved_name'])
        if os.path.exists(file_path):
            os.remove(file_path)
    elif record['msg_type'] == 'folder':
        import shutil
        folder_path = record['saved_name']
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        cursor.execute('DELETE FROM messages WHERE folder_id = ?', (record['folder_id'],))
    
    cursor.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    conn.commit()
    
    return jsonify({'message': '删除成功'}), 200

@app.route('/api/user/info', methods=['GET'])
@login_required
def get_user_info():
    return jsonify({
        'user_id': session['user_id'],
        'username': session['username']
    }), 200

@app.after_request
def add_cache_headers(response):
    if 'static' in request.path or request.path.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2', '.ttf', '.eot')):
        response.cache_control.max_age = 86400
        response.cache_control.public = True
    return response

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    init_db()
    
    print("=" * 50)
    print("Web 文件传输助手启动成功!")
    print(f"数据库位置: {app.config['DATABASE']}")
    print(f"上传目录: {app.config['UPLOAD_FOLDER']}")
    print("请在浏览器中访问: http://127.0.0.1:5000")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
