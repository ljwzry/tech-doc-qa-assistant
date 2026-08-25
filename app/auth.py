"""API 鉴权模块 — Bearer Token 验证"""
from fastapi import Header, HTTPException, Depends
from app.config import settings


async def verify_api_key(authorization: str = Header(None)):
    """验证 Bearer Token，仅当 AUTH_ENABLED=true 时生效"""
    if not settings.auth_enabled:
        return

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="缺少 Authorization 头，请使用 Bearer Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authorization 格式错误，应为 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    if token != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True
