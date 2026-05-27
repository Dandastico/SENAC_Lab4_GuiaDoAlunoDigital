from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.cms.models import Artigo, ArtigoStatus, Categoria, Secao

class CategoriaRepository:
    def __init__(self, session:AsyncSession):
        self.session = session

    async def get(self, categoria_id: int) -> Categoria | None:
        return await self.session.get(Categoria, categoria_id)

    async def get_by_slug(self, slug: str) -> Categoria | None:
        stmt = select(Categoria).where(Categoria.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()
    
    async def listar(self, skip: int, limit: int) -> list[Categoria]:
        stmt = (
            select(Categoria)
            .orger_by(Categoria.posicao, Categoria.nome)
            .offset(skip)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
    
    async def contar(self) -> int:
        stmt = select(func.count()).select_from(Categoria)
        return (await self.session.execute(stmt)).scalar_one()
    
    async def add(self, categoria: Categoria) -> Categoria:
        self.session.add(categoria)
        await self.session.flush()
        await self.session.refresh(categoria)
        return categoria
    
    async def delete(self, categoria: Categoria) -> None:
        await self.session.delete(categoria)


class SecaoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get(self, secao_id: int) -> Secao | None:
        return await self.session.get(Secao, secao_id)
    
    async def get_by_slug_na_categoria(
            self, categoria_id: int, slug: str
    ) -> Secao | None:
        stmt = select(Secao).where(
            Secao.categoria_id == categoria_id,
            Secao.slug == slug
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
    
    async def listar_da_categoria(self, categoria_id: int) -> list[Secao]:
        stmt = (
            select(Secao)
            .where(Secao.categoria_id == categoria_id)
            .order_by(Secao.posicao, Secao.nome)
        )
        return list((await self.session.execute(stmt)).scalars().all())
    
    async def add(self, secao: Secao) -> Secao:
        self.session.add(secao)
        await self.session.flush()
        await self.session.refresh(secao)
        return secao
    
    async def delete(self, secao: Secao) -> None:
        await self.session.delete(secao)


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