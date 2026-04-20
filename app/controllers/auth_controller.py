# -*- coding: utf-8 -*-
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from ..services import AuthService


auth_router = APIRouter(tags=['auth'])
auth_service = AuthService()


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


def get_current_user(request: Request) -> Optional[dict]:
    user_id = request.session.get('user_id')
    username = request.session.get('username')
    if not user_id:
        return None
    return {'user_id': user_id, 'username': username}


def login_required(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail='请先登录')
    return user


@auth_router.get('/', response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url='/chat', status_code=302)
    return RedirectResponse(url='/login', status_code=302)


@auth_router.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse('login.html', {'request': request})


@auth_router.get('/register', response_class=HTMLResponse)
async def register_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse('register.html', {'request': request})


@auth_router.get('/chat', response_class=HTMLResponse)
async def chat(request: Request, user: dict = Depends(login_required)):
    templates = request.app.state.templates
    return templates.TemplateResponse('chat.html', {
        'request': request,
        'username': user['username']
    })


@auth_router.post('/api/register')
async def register(data: RegisterRequest):
    success, message, user_id = auth_service.register(data.username, data.password)
    
    if success:
        return {'message': message}
    else:
        raise HTTPException(status_code=400, detail=message)


@auth_router.post('/api/login')
async def login(request: Request, data: LoginRequest):
    success, message, user = auth_service.login(data.username, data.password)
    
    if success:
        request.session['user_id'] = user.id
        request.session['username'] = user.username
        return {'message': message, 'username': user.username}
    else:
        raise HTTPException(status_code=401, detail=message)


@auth_router.post('/api/logout')
async def logout(request: Request):
    request.session.clear()
    return {'message': '已退出登录'}


@auth_router.get('/api/user/info')
async def get_user_info(user: dict = Depends(login_required)):
    return {
        'user_id': user['user_id'],
        'username': user['username']
    }
