from fastapi import FastAPI
from app.cms.router import router as cms_router

app = FastAPI(title="Guia Estudantil FACSENAC-DF – API")
app.include_router(cms_router)

@app.get("/health")
async def health():
    return {"status": "ok"}