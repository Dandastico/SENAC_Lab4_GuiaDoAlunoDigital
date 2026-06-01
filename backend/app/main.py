from fastapi import FastAPI
from app.cms.router import (
    router as artigos_router,
    admin_artigos_router,
    categorias_router,
    secoes_router
)
from app.auth.router import auth_router
from sqlalchemy.exc import IntegrityError
from app.errors import integrity_error_handler

app = FastAPI(title="Guia Estudantil FACSENAC-DF – API")

app.include_router(auth_router)
app.include_router(categorias_router)
app.include_router(secoes_router)
app.include_router(artigos_router)
app.include_router(admin_artigos_router)

app.add_exception_handler(IntegrityError, integrity_error_handler)

@app.get("/health")
async def health():
    return {"status": "ok"}