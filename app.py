import os
import uuid
import sqlite3
import zipfile
import io
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, session, send_file, render_template, redirect, url_for, Response
import bcrypt

app = Flask(__name__)
app.secret_key = 'file-transfer-helper-secret-key-2024'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.sqlite')

def get_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
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
        conn.close()
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
    conn.close()
    
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

@app.route('/api/messages', methods=['GET'])
@login_required
def get_messages():
    user_id = session['user_id']
    since = request.args.get('since', '0')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, msg_type, content, filename, file_size, relative_path, folder_id, file_count, created_at
        FROM messages 
        WHERE user_id = ? AND id > ? AND msg_type != 'folder_file'
        ORDER BY created_at ASC
    ''', (user_id, since))
    messages = cursor.fetchall()
    conn.close()
    
    msg_list = []
    for m in messages:
        msg = {
            'id': m['id'],
            'type': m['msg_type'],
            'time': m['created_at']
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
    date = request.args.get('date', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = 'SELECT id, msg_type, content, filename, file_size, relative_path, folder_id, file_count, created_at FROM messages WHERE user_id = ? AND msg_type != \'folder_file\''
    params = [user_id]
    
    if keyword:
        query += ' AND (content LIKE ? OR filename LIKE ? OR relative_path LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    
    if date:
        query += ' AND DATE(created_at) = ?'
        params.append(date)
    
    if start_date:
        query += ' AND DATE(created_at) >= ?'
        params.append(start_date)
    
    if end_date:
        query += ' AND DATE(created_at) <= ?'
        params.append(end_date)
    
    query += ' ORDER BY created_at DESC LIMIT 100'
    
    cursor.execute(query, params)
    messages = cursor.fetchall()
    conn.close()
    
    msg_list = []
    for m in messages:
        msg = {
            'id': m['id'],
            'type': m['msg_type'],
            'time': m['created_at']
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
    
    if len(content) > 10000:
        return jsonify({'error': '消息内容过长'}), 400
    
    user_id = session['user_id']
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (user_id, msg_type, content)
            VALUES (?, ?, ?)
        ''', (user_id, 'text', content))
        conn.commit()
        msg_id = cursor.lastrowid
        cursor.execute('SELECT created_at FROM messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'message': '发送成功',
            'msg': {
                'id': msg_id,
                'type': 'text',
                'content': content,
                'time': row['created_at']
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
            INSERT INTO messages (user_id, msg_type, filename, saved_name, file_size, relative_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, 'file', original_filename, saved_name, file_size, relative_path))
        conn.commit()
        msg_id = cursor.lastrowid
        cursor.execute('SELECT created_at FROM messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'message': '发送成功',
            'msg': {
                'id': msg_id,
                'type': 'file',
                'filename': original_filename,
                'file_size': file_size,
                'file_id': msg_id,
                'relative_path': relative_path,
                'time': row['created_at']
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
            INSERT INTO messages (user_id, msg_type, filename, saved_name, file_size, folder_id, file_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, 'folder', folder_name, folder_path, total_size, folder_id, file_count))
        
        msg_id = cursor.lastrowid
        cursor.execute('SELECT created_at FROM messages WHERE id = ?', (msg_id,))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': '发送成功',
            'msg': {
                'id': msg_id,
                'type': 'folder',
                'filename': folder_name,
                'file_size': total_size,
                'file_count': file_count,
                'folder_id': folder_id,
                'time': row['created_at']
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
    conn.close()
    
    if not record:
        return jsonify({'error': '文件夹不存在或无权访问'}), 404
    
    folder_path = record['saved_name']
    folder_name = record['filename']
    
    if not os.path.exists(folder_path):
        return jsonify({'error': '文件夹不存在'}), 404
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    
    return Response(
        zip_buffer.getvalue(),
        mimetype='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename="{folder_name}.zip"',
            'Content-Length': str(zip_buffer.getbuffer().nbytes)
        }
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
    conn.close()
    
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
        conn.close()
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
    conn.close()
    
    return jsonify({'message': '删除成功'}), 200

@app.route('/api/user/info', methods=['GET'])
@login_required
def get_user_info():
    return jsonify({
        'user_id': session['user_id'],
        'username': session['username']
    }), 200

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
