# -*- coding: utf-8 -*-
import json
import base64
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
import itsdangerous
from itsdangerous import TimestampSigner, BadSignature
from ..services import AuthService
from ..websocket_manager import ws_manager


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
async def chat(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url='/login', status_code=302)
    templates = request.app.state.templates
    return templates.TemplateResponse('chat.html', {
        'request': request,
        'username': user['username']
    })


@auth_router.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    user_id = None
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("WebSocket: 开始接受连接")
        await websocket.accept()
        logger.info("WebSocket: 连接已接受")
        
        from ..config import get_config
        config = get_config()
        
        session_cookie = websocket.cookies.get('session', '')
        logger.info(f"WebSocket: session cookie = {session_cookie[:20] if session_cookie else 'None'}...")
        
        if not session_cookie:
            logger.warning("WebSocket: 没有 session cookie")
            await websocket.send_text(json.dumps({'type': 'error', 'message': '未登录'}, ensure_ascii=False))
            await websocket.close()
            return
        
        try:
            signer = TimestampSigner(config.SECRET_KEY)
            data = session_cookie.encode('utf-8')
            data = signer.unsign(data, max_age=config.SESSION_MAX_AGE)
            session_dict = json.loads(base64.b64decode(data))
            user_id = session_dict.get('user_id')
            logger.info(f"WebSocket: 解析到 user_id = {user_id}")
            
            if not user_id:
                logger.warning("WebSocket: user_id 为空")
                await websocket.send_text(json.dumps({'type': 'error', 'message': '未登录'}, ensure_ascii=False))
                await websocket.close()
                return
        except Exception as e:
            logger.error(f"WebSocket: session 解析失败 - {e}")
            await websocket.send_text(json.dumps({'type': 'error', 'message': '会话无效'}, ensure_ascii=False))
            await websocket.close()
            return
        
        ws_manager.connect(websocket, user_id)
        logger.info(f"WebSocket: 用户 {user_id} 连接成功")
        await websocket.send_text(json.dumps({'type': 'connected'}, ensure_ascii=False))
        
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get('type') == 'ping':
                    await websocket.send_text(json.dumps({'type': 'pong'}, ensure_ascii=False))
            except WebSocketDisconnect:
                logger.info(f"WebSocket: 用户 {user_id} 断开连接")
                break
            except Exception as e:
                logger.error(f"WebSocket: 消息处理错误 - {e}")
                continue
                
    except Exception as e:
        logger.error(f"WebSocket: 异常 - {e}", exc_info=True)
    finally:
        if user_id:
            ws_manager.disconnect(websocket, user_id)


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
