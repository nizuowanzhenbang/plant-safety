"""依赖注入：DB 会话 + JWT 鉴权 + 角色权限拦截"""
from datetime import datetime, timedelta
from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise credentials_exception
    return user


ROLE_LEVEL = {
    UserRole.VIEWER: 1,
    UserRole.OPERATOR: 2,
    UserRole.SAFETY_OFFICER: 3,
    UserRole.ADMIN: 4,
}


def require_roles(*roles: UserRole) -> Callable[..., User]:
    """权限拦截工厂：要求当前用户角色在 roles 内。

    用法：`current: User = Depends(require_roles(UserRole.SAFETY_OFFICER, UserRole.ADMIN))`
    """
    allowed = set(roles)

    def _checker(current: User = Depends(get_current_user)) -> User:
        if current.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要角色：{','.join(r.value for r in allowed)}",
            )
        return current

    return _checker


def require_min_role(min_role: UserRole) -> Callable[..., User]:
    """权限拦截工厂：要求当前用户角色 >= min_role（按 ROLE_LEVEL 等级排序）。"""
    threshold = ROLE_LEVEL[min_role]

    def _checker(current: User = Depends(get_current_user)) -> User:
        if ROLE_LEVEL.get(current.role, 0) < threshold:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要至少 {min_role.value} 角色",
            )
        return current

    return _checker
