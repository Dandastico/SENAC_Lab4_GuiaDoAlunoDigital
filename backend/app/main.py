from fastapi import FastAPI
from app.cms.router import router as cms_router
from sqlalchemy.exc import IntegrityError
from app.errors import integrity_error_handler

app = FastAPI(title="Guia Estudantil FACSENAC-DF – API")
app.include_router(cms_router)

app.add_exception_handler(IntegrityError, integrity_error_handler)

@app.get("/health")
async def health():
    return {"status": "ok"}