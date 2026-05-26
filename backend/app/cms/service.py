from datetime import datetime, timezone
from uuid import UUID
from slugify import slugify
from app.cms.models import Artigo, ArtigoStatus
from app.cms.schemas import ArtigoCreate, ArtigoUpdate
from app.cms.repository import ArtigoRepository

class ArtigoService:
    def __init__(self, repo: ArtigoRepository):
        self.repo = repo

    async def criar(self, dados: ArtigoCreate, autor_id: UUID) -> Artigo:
        slug = await self._slug_unico(dados.titulo)
        publicado_em = (
            datetime.now(timezone.utc) if dados.status == ArtigoStatus.publicado else None
        )
        artigo = Artigo(
            titulo=dados.titulo,
            slug=slug,
            conteudo=dados.conteudo,
            secao_id=dados.secao_id,
            status=dados.status,
            agendado_para=dados.agendado_para,
            publicado_em=publicado_em,
            autor_id=autor_id
        )
        return await self.repo.add(artigo)
    
    async def atualizar(self, artigo: Artigo, dados: ArtigoUpdate) -> Artigo:
        update = dados.model_dump(exclude_unset=True)
        if "titulo" in update and update["titulo"] != artigo.titulo:
            update["slug"] = await self._slug_unico(update["titulo"])
        if update.get("status") == ArtigoStatus.publicado and not artigo.publicado_em:
            update["publicado_em"] = datetime.now(timezone.utc)
        for k, v in update.items():
            setattr(artigo, k, v)
        await self.repo.session.flush()
        await self.repo.session.refresh(artigo)
        return artigo
    
    async def _slug_unico(self, titulo: str) -> str:
        base = slugify(titulo)
        slug, n = base, 1
        while await self.repo.get_by_slug(slug):
            n += 1
            slug = f"{base}-{n}"
        return slug