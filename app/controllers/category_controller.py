# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
from ..services import CategoryService
from .auth_controller import login_required


category_bp = Blueprint('category', __name__)
category_service = CategoryService()


@category_bp.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    user_id = session['user_id']
    categories = category_service.get_user_categories(user_id)
    return jsonify({'categories': categories}), 200


@category_bp.route('/api/categories', methods=['POST'])
@login_required
def create_category():
    user_id = session['user_id']
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    name = data.get('name', '')
    parent_id = data.get('parent_id')
    
    success, message, category = category_service.create_category(
        user_id, name, parent_id
    )
    
    if success:
        return jsonify({'message': message, 'category': category}), 201
    else:
        return jsonify({'error': message}), 400


@category_bp.route('/api/categories/<int:category_id>', methods=['PUT'])
@login_required
def update_category(category_id):
    user_id = session['user_id']
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    name = data.get('name', '')
    
    success, message = category_service.update_category(
        category_id, user_id, name
    )
    
    if success:
        return jsonify({'message': message}), 200
    else:
        return jsonify({'error': message}), 400


@category_bp.route('/api/categories/<int:category_id>', methods=['DELETE'])
@login_required
def delete_category(category_id):
    user_id = session['user_id']
    
    success, message = category_service.delete_category(category_id, user_id)
    
    if success:
        return jsonify({'message': message}), 200
    else:
        return jsonify({'error': message}), 400
