"""
全局统一响应封装
所有接口统一返回结构：
{
    "code": 0,
    "msg": "success",
    "data": {...}
}
"""

from typing import Any, Generic, Optional, TypeVar

from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiResult(BaseModel, Generic[T]):
    """统一响应模型（用于 OpenAPI 文档展示）"""
    code: int = 0
    msg: str = "success"
    data: Optional[T] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ============== 业务码定义（按需扩展） ==============
CODE_OK = 0
CODE_BAD_REQUEST = 400
CODE_UNAUTHORIZED = 401
CODE_FORBIDDEN = 403
CODE_NOT_FOUND = 404
CODE_CONFLICT = 409
CODE_VALIDATION = 422
CODE_INTERNAL = 500


def success(data: Any = None, msg: str = "success") -> JSONResponse:
    """返回成功响应"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": CODE_OK,
            "msg": msg,
            "data": jsonable_encoder(data),
        },
    )


def fail(
    code: int = CODE_BAD_REQUEST,
    msg: str = "操作失败",
    data: Any = None,
    http_status: int = status.HTTP_200_OK,
) -> JSONResponse:
    """返回失败响应（HTTP 仍为 200，业务码区分；保持前端拦截器统一）"""
    return JSONResponse(
        status_code=http_status,
        content={
            "code": code,
            "msg": msg,
            "data": jsonable_encoder(data),
        },
    )
