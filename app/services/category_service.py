# -*- coding: utf-8 -*-
from typing import List, Optional, Tuple
from ..repositories import CategoryRepository
from ..models import Category


class CategoryService:
    def __init__(self, category_repo: CategoryRepository = None):
        self._category_repo = category_repo or CategoryRepository()
    
    def get_user_categories(self, user_id: int) -> List[dict]:
        categories = self._category_repo.find_by_user(user_id)
        return [
            {'id': c.id, 'name': c.name, 'parent_id': c.parent_id}
            for c in categories
        ]
    
    def create_category(
        self, user_id: int, name: str, parent_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[dict]]:
        name = name.strip() if name else ''
        
        if not name:
            return False, '目录名称不能为空', None
        
        try:
            category_id = self._category_repo.create(user_id, name, parent_id)
            return True, '创建成功', {
                'id': category_id, 
                'name': name, 
                'parent_id': parent_id
            }
        except Exception:
            return False, '创建失败', None
    
    def update_category(
        self, category_id: int, user_id: int, name: str
    ) -> Tuple[bool, str]:
        name = name.strip() if name else ''
        
        if not name:
            return False, '目录名称不能为空'
        
        category = self._category_repo.find_by_id(category_id, user_id)
        if not category:
            return False, '目录不存在'
        
        if self._category_repo.update(category_id, name):
            return True, '更新成功'
        return False, '更新失败'
    
    def delete_category(self, category_id: int, user_id: int) -> Tuple[bool, str]:
        category = self._category_repo.find_by_id(category_id, user_id)
        if not category:
            return False, '目录不存在'
        
        if self._category_repo.delete(category_id):
            return True, '删除成功'
        return False, '删除失败'
