from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from app.config import configuracoes
from typing import AsyncGenerator

engine = create_async_engine(configuracoes.database_url, pool_pre_ping=True)
SessaoLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_sessao() -> AsyncGenerator[AsyncSession, None]:
    async with SessaoLocal() as sessao:
        yield sessao