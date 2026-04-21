# -*- coding: utf-8 -*-
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    _instance: 'ConnectionManager' = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections: Dict[int, Set[WebSocket]] = {}
        return cls._instance
    
    def connect(self, websocket: WebSocket, user_id: int):
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(websocket)
        logger.info(f"WebSocket connected for user {user_id}, total: {len(self._connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_to_user(self, user_id: int, message: dict):
        if user_id not in self._connections:
            return
        
        message_json = json.dumps(message, ensure_ascii=False)
        dead_connections = set()
        
        for websocket in self._connections[user_id]:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message: {e}")
                dead_connections.add(websocket)
        
        for ws in dead_connections:
            self._connections[user_id].discard(ws)
    
    async def broadcast_new_message(self, user_id: int, message: dict):
        await self.send_to_user(user_id, {
            'type': 'new_message',
            'data': message
        })
    
    async def broadcast_message_deleted(self, user_id: int, message_id: int):
        await self.send_to_user(user_id, {
            'type': 'message_deleted',
            'data': {'id': message_id}
        })
    
    async def broadcast_category_updated(self, user_id: int):
        await self.send_to_user(user_id, {
            'type': 'category_updated'
        })
    
    def get_connection_count(self, user_id: int) -> int:
        return len(self._connections.get(user_id, set()))


ws_manager = ConnectionManager()
