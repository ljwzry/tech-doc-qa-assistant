"""API 响应统一工具类 + 路径安全校验"""
import os
import re
from pathlib import Path
from fastapi import HTTPException
from typing import Any, Optional

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/docs")
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt"}


def _parse_file_size(size_str: str) -> int:
    """解析文件大小字符串，支持 '50MB'、'1GB'、'100KB' 等格式"""
    size_str = size_str.strip().upper()
    units = {
        'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3
    }
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                value = float(size_str[:-len(unit)].strip())
                return int(value * multiplier)
            except ValueError:
                break
    # 纯数字默认按字节处理
    try:
        return int(size_str)
    except ValueError:
        return 50 * 1024 * 1024  # 默认 50MB


MAX_FILE_SIZE = _parse_file_size(os.getenv("MAX_FILE_SIZE", "50MB"))


def success_response(data: Any = None, message: str = "操作成功") -> dict:
    """统一成功响应格式"""
    return {"code": 0, "message": message, "data": data}


def error_response(message: str, code: int = 1) -> dict:
    """统一错误响应格式"""
    return {"code": code, "message": message}


def sanitize_filename(filename: str) -> str:
    """清理文件名，防止路径遍历攻击

    规则：
    - 不允许包含路径分隔符（/ \\ ..）
    - 不允许空文件名
    - 移除所有 '..' 和路径分隔符
    """
    if not filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 检查是否包含危险字符
    dangerous = ["..", "/", "\\", "\x00"]
    for d in dangerous:
        if d in filename:
            raise HTTPException(status_code=400, detail=f"文件名包含非法字符: {d}")

    # 只保留文件名部分
    safe_name = os.path.basename(filename)

    if not safe_name or safe_name in (".", ".."):
        raise HTTPException(status_code=400, detail="无效的文件名")

    return safe_name


def sanitize_project_name(project: str) -> str:
    """清理项目名，防止路径遍历"""
    if not project:
        raise HTTPException(status_code=400, detail="项目名不能为空")

    # 检查危险字符
    dangerous = ["..", "/", "\\", "\x00"]
    for d in dangerous:
        if d in project:
            raise HTTPException(status_code=400, detail=f"项目名包含非法字符: {d}")

    # 项目名不应包含空格
    project = project.strip()
    if not project:
        raise HTTPException(status_code=400, detail="项目名不能为空")

    return project


def validate_file_extension(filename: str) -> str:
    """校验文件扩展名"""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}")
    return ext


def validate_file_size(file_size: int) -> None:
    """校验文件大小，禁止超大文件"""
    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"文件过大，最大允许 {max_mb:.0f}MB")


def get_safe_path(base_dir: str, *parts: str) -> str:
    """构建安全的文件路径，确保不会越界"""
    base = Path(base_dir).resolve()
    target = base.joinpath(*parts).resolve()

    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="非法路径访问")

    return str(target)
