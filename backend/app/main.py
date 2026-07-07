"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, SessionLocal, Base
from app.models.user import User, UserRole
from app.models.hazard import Hazard
from app.models.ticket import WorkTicket, OperationTicket
from app.models.safety_check import SafetyCheckPlan, SafetyCheckRecord
from app.api import (
    auth, hazards, dashboard, integration,
    work_tickets, operation_tickets, safety_checks, ws,
)
from app.api.deps import hash_password

# 确保所有模型在建表前已被导入
_ = (User, Hazard, WorkTicket, OperationTicket, SafetyCheckPlan, SafetyCheckRecord)


def _create_default_admin(db) -> None:
    if db.query(User).filter(User.username == "admin").first():
        return
    admin = User(
        username="admin",
        hashed_password=hash_password("admin123"),
        role=UserRole.ADMIN,
        department="安环部",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(admin)
    db.commit()
    print("[启动] 默认管理员账户已创建：admin / admin123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _create_default_admin(db)
    finally:
        db.close()
    print(f"[启动] {settings.APP_NAME} v{settings.APP_VERSION} 已就绪")
    yield
    print("[关闭] 应用正在关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="发电厂安全生产管理系统 - 隐患排查 + 两票管理 + 安全检查 + 实时推送",
    lifespan=lifespan,
)

allowed = settings.ALLOWED_ORIGINS or [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(hazards.router)
app.include_router(dashboard.router)
app.include_router(integration.router)
app.include_router(work_tickets.router)
app.include_router(operation_tickets.router)
app.include_router(safety_checks.router)
app.include_router(ws.router)


@app.get("/health", tags=["系统"])
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/", tags=["系统"])
def root():
    return {"message": f"欢迎使用 {settings.APP_NAME}", "docs": "/docs"}
