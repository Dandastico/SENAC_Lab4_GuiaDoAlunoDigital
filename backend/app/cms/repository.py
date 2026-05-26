from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.cms.models import Artigo, ArtigoStatus

class ArtigoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get(self, artigo_id: int) -> Artigo | None:
        return await self.session.get(Artigo, artigo_id)
    
    async def get_by_slug(self, slug: str) -> Artigo | None:
        stmt = select(Artigo).where(Artigo.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()
    
    async def list_publicados(self, skip: int, limit: int):
        stmt = (
            select(Artigo)
            .where(Artigo.status == ArtigoStatus.publicado)
            .order_by(Artigo.publicado_em.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def count_publicados(self) -> int:
        stmt = select(func.count()).select_from(Artigo).where(
            Artigo.status == ArtigoStatus.publicado
        )
        return (await self.session.execute(stmt)).scalar_one()
    
    async def add(self, artigo: Artigo) -> Artigo:
        self.session.add(artigo)
        await self.session.flush()
        await self.session.refresh(artigo)
        return artigo
    
    async def delete(self, artigo: Artigo) -> None:
        await self.session.delete(artigo)