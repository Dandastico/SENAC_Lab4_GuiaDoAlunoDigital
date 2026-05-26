from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
import asyncpg

async def integrity_error_handler(request: Request, exc: IntegrityError):
    orig = exc.orig
    if isinstance(orig, asyncpg.UniqueViolationError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(orig, (asyncpg.CheckViolationError, asyncpg.ForeignKeyViolationError)):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_409_CONFLICT
    return JSONResponse(
        status_code=status.code,
        content={"detail": str(orig), "info": str(exc.orig)}
    )