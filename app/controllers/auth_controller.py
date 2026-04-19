# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from functools import wraps
from ..services import AuthService


auth_bp = Blueprint('auth', __name__)
auth_service = AuthService()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('auth.chat'))
    return redirect(url_for('auth.login_page'))


@auth_bp.route('/login')
def login_page():
    return render_template('login.html')


@auth_bp.route('/register')
def register_page():
    return render_template('register.html')


@auth_bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html', username=session.get('username'))


@auth_bp.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    username = data.get('username', '')
    password = data.get('password', '')
    
    success, message, user_id = auth_service.register(username, password)
    
    if success:
        return jsonify({'message': message}), 201
    else:
        return jsonify({'error': message}), 400


@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    username = data.get('username', '')
    password = data.get('password', '')
    
    success, message, user = auth_service.login(username, password)
    
    if success:
        session['user_id'] = user.id
        session['username'] = user.username
        return jsonify({'message': message, 'username': user.username}), 200
    else:
        return jsonify({'error': message}), 401


@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': '已退出登录'}), 200


@auth_bp.route('/api/user/info', methods=['GET'])
@login_required
def get_user_info():
    return jsonify({
        'user_id': session['user_id'],
        'username': session['username']
    }), 200
