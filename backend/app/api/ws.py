"""WebSocket 实时通知

连接：ws://host:8000/ws/notifications?token=<JWT>
事件载荷：{event, title, message, payload, ts}
"""
import asyncio
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.user import User

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.active.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self.active:
                self.active.remove(ws)

    async def broadcast(self, event: str, title: str, message: str, payload: Optional[dict] = None) -> None:
        data = json.dumps({
            "event": event,
            "title": title,
            "message": message,
            "payload": payload or {},
            "ts": datetime.utcnow().isoformat(),
        }, ensure_ascii=False, default=str)
        async with self._lock:
            targets = list(self.active)
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                await self.disconnect(ws)

manager = ConnectionManager()


async def push(event: str, title: str, message: str, payload: Optional[dict] = None) -> None:
    """async helper：业务端点用 BackgroundTasks.add_task(push, ...) 即可异步广播。"""
    await manager.broadcast(event, title, message, payload)


def _verify_token(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user and user.is_active:
            return user
        return None
    finally:
        db.close()


@router.websocket("/ws/notifications")
async def notifications_ws(ws: WebSocket, token: Optional[str] = Query(None)):
    user = _verify_token(token)
    if not user:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect(ws)
    try:
        await ws.send_text(json.dumps({
            "event": "connected",
            "title": "已连接",
            "message": f"欢迎 {user.username}",
            "payload": {"role": user.role.value},
            "ts": datetime.utcnow().isoformat(),
        }, ensure_ascii=False))
        # 心跳：客户端如果发文本，原样回；30s 无消息也保持连接
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if msg == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"event": "heartbeat", "ts": datetime.utcnow().isoformat()}))
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
