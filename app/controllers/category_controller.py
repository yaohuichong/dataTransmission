# -*- coding: utf-8 -*-
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from ..services import CategoryService
from .auth_controller import login_required


category_router = APIRouter(tags=['categories'])
category_service = CategoryService()


class CreateCategoryRequest(BaseModel):
    name: str
    parent_id: Optional[int] = None


class UpdateCategoryRequest(BaseModel):
    name: str


@category_router.get('/api/categories')
async def get_categories(
    request: Request,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    categories = category_service.get_user_categories(user_id)
    return {'categories': categories}


@category_router.post('/api/categories')
async def create_category(
    request: Request,
    data: CreateCategoryRequest,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message, category = category_service.create_category(
        user_id, data.name, data.parent_id
    )
    
    if success:
        return {'message': message, 'category': category}
    else:
        raise HTTPException(status_code=400, detail=message)


@category_router.put('/api/categories/{category_id}')
async def update_category(
    request: Request,
    category_id: int,
    data: UpdateCategoryRequest,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message = category_service.update_category(
        category_id, user_id, data.name
    )
    
    if success:
        return {'message': message}
    else:
        raise HTTPException(status_code=400, detail=message)


@category_router.delete('/api/categories/{category_id}')
async def delete_category(
    request: Request,
    category_id: int,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message = category_service.delete_category(category_id, user_id)
    
    if success:
        return {'message': message}
    else:
        raise HTTPException(status_code=400, detail=message)


@category_router.get('/api/categories/trash')
async def get_category_trash(
    request: Request,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    categories = category_service.get_trash(user_id)
    return {'categories': categories}


@category_router.post('/api/categories/trash/{category_id}/restore')
async def restore_category(
    request: Request,
    category_id: int,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message = category_service.restore_category(category_id, user_id)
    
    if success:
        return {'message': message}
    else:
        raise HTTPException(status_code=400, detail=message)


@category_router.delete('/api/categories/trash/{category_id}')
async def permanent_delete_category(
    request: Request,
    category_id: int,
    user: dict = Depends(login_required)
):
    user_id = user['user_id']
    
    success, message = category_service.permanent_delete_category(category_id, user_id)
    
    if success:
        return {'message': message}
    else:
        raise HTTPException(status_code=400, detail=message)
