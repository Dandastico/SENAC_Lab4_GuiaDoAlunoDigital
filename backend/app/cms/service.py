from datetime import datetime, timezone
from uuid import UUID
from slugfy import slugify
from app.cms.models import Artigo, ArtigoStatus
from app.cms.schemas import ArtigoCreate, ArtigoUpdate
from app.cms.repository import ArtigoRepository

class ArtigoService:
    def __init__(self, repo: ArtigoRepository):
        self.repo - repo

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
    
    