from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.cms.models import Artigo, ArtigoStatus, Categoria, Secao

class CategoriaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, categoria_id: int) -> Categoria | None:
        return await self.session.get(Categoria, categoria_id)

    async def get_by_slug(self, slug: str) -> Categoria | None:
        stmt = select(Categoria).where(Categoria.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()
    
    async def listar(self, skip: int, limit: int) -> list[Categoria]:
        stmt = (
            select(Categoria)
            .order_by(Categoria.posicao, Categoria.nome)
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

    async def listar(self, categoria_id: int | None = None) -> list[Secao]:
        # Lista seções; quando `categoria_id` é None, devolve todas as seções
        # (visão global usada pelo painel admin). `categoria_id` entra como
        # ordenação primária para manter as seções agrupadas por categoria.
        stmt = select(Secao)
        if categoria_id is not None:
            stmt = stmt.where(Secao.categoria_id == categoria_id)
        stmt = stmt.order_by(Secao.categoria_id, Secao.posicao, Secao.nome)
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
        stmt = select(Artigo).where(
            Artigo.slug == slug,
            Artigo.status == ArtigoStatus.publicado
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def existe_slug(self, slug: str, excluir_id: int | None = None) -> bool:
        # Verifica se o slug já está em uso em QUALQUER status (rascunho,
        # publicado, escondido, agendado).
        stmt = select(func.count()).select_from(Artigo).where(Artigo.slug == slug)
        if excluir_id is not None:
            stmt = stmt.where(Artigo.id != excluir_id)
        return (await self.session.execute(stmt)).scalar_one() > 0
    
    async def list_publicados(self, skip: int, limit: int):
        stmt = (
            select(Artigo)
            .where(Artigo.status == ArtigoStatus.publicado)
            .order_by(Artigo.publicado_em.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def count_publicados(self) -> int:
        stmt = select(func.count()).select_from(Artigo).where(
            Artigo.status == ArtigoStatus.publicado
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def listar_admin(
        self,
        skip: int,
        limit: int,
        status: ArtigoStatus | None = None,
        secao_id: int | None = None,
    ) -> list[Artigo]:
        # Visão administrativa: enxerga TODOS os status. `status` e `secao_id`
        # são filtros opcionais — quando None, não restringem o resultado.
        stmt = select(Artigo)
        if status is not None:
            stmt = stmt.where(Artigo.status == status)
        if secao_id is not None:
            stmt = stmt.where(Artigo.secao_id == secao_id)
        stmt = stmt.order_by(Artigo.atualizado_em.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def contar_admin(
        self,
        status: ArtigoStatus | None = None,
        secao_id: int | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Artigo)
        if status is not None:
            stmt = stmt.where(Artigo.status == status)
        if secao_id is not None:
            stmt = stmt.where(Artigo.secao_id == secao_id)
        return (await self.session.execute(stmt)).scalar_one()

    async def add(self, artigo: Artigo) -> Artigo:
        self.session.add(artigo)
        await self.session.flush()
        await self.session.refresh(artigo)
        return artigo
    
    async def delete(self, artigo: Artigo) -> None:
        await self.session.delete(artigo)