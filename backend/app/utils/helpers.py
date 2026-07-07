"""通用工具函数"""
from typing import Any, Optional


def api_response(data: Any = None, message: str = "ok", code: int = 200) -> dict:
    return {"code": code, "message": message, "data": data}


def paginate_response(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 0,
    }


def generate_hazard_code(seq: int) -> str:
    """生成隐患编号：YH-YYYYMMDD-NNNN"""
    from datetime import datetime
    return f"YH-{datetime.now().strftime('%Y%m%d')}-{seq:04d}"


def generate_work_ticket_code(seq: int) -> str:
    """生成工作票号：GZ-YYYYMMDD-NNNN"""
    from datetime import datetime
    return f"GZ-{datetime.now().strftime('%Y%m%d')}-{seq:04d}"


def generate_operation_ticket_code(seq: int) -> str:
    """生成操作票号：CZ-YYYYMMDD-NNNN"""
    from datetime import datetime
    return f"CZ-{datetime.now().strftime('%Y%m%d')}-{seq:04d}"


def generate_safety_check_code(seq: int) -> str:
    """生成安全检查记录编号：AJ-YYYYMMDD-NNNN"""
    from datetime import datetime
    return f"AJ-{datetime.now().strftime('%Y%m%d')}-{seq:04d}"
