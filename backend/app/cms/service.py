from datetime import datetime, timezone
from uuid import UUID
from slugify import slugify
from app.cms.models import Artigo, ArtigoStatus, Categoria, Secao
from app.cms.schemas import ArtigoCreate, ArtigoUpdate, CategoriaCreate, CategoriaUpdate, SecaoCreate, SecaoUpdate
from app.cms.repository import ArtigoRepository, SecaoRepository, CategoriaRepository

class CategoriaService:
    def __init__(self, repo: CategoriaRepository):
        self.repo = repo
    
    async def criar(self, dados: CategoriaCreate) -> Categoria:
        slug = await self._slug_unico(dados.nome)
        categoria = Categoria(
            nome=dados.nome,
            slug=slug,
            descricao=dados.descricao,
            posicap=dados.posicao
        )
        return await self.repo.add(categoria)
    
    async def atualizar(
            self, categoria: Categoria, dados: CategoriaUpdate
    ) -> Categoria:
        update = dados.model_dump(exclude_unset=True)
        if "nome" in update and update["nome"] != categoria.nome:
            update["slug"] = await self._slug_unico(
                update["nome"], excluir_id=categoria.id
            )
        for k, v in update.items():
            setattr(categoria, k, v)
        await self.repo.flush()
        await self.repo.refresh(categoria)
        return categoria
    
    async def deletar(self, categoria: Categoria) -> None:
        stmt = (
            select(func.count())
            .select_from(Artigo)
            .join(Secao, Artigo.secao_id == Secao.id)
            .where(Secao.categoria_id == categoria.id)
        )
        qtd = (await self.repo.session.execute(stmt)).scalar_one()
        if qtd > 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Categoria tem {qtd} artigo(s) vinculado(s). "
                "Mova ou apague os artigos antes de remover a categoria."
            )
        await self.repo.delete(categoria)

    async def _slug_unico(self, nome: str, excluir_id: int | None = None) -> str:
        base = slugify(nome)
        slug, n = base, 1
        while True:
            existence = await self.repo.get_byr_slug(slug)
            if existence is None or existence.id == excluir_id:
                return slug
            n += 1
            slug = f"{base}-{n}"


class SecaoService:
    def __init__(self, repo: SecaoRepository, cat_repo: CategoriaRepository):
        self.repo = repo
        self.cat_repo = cat_repo

    async def criar(self, dados: SecaoCreate) -> Secao:
        if not await self.cat_repo.get(dados.categoria_id):
            raise ValueError(f"Categoria {dados.categoria_id} não existe")
        slug = await self._slug_unico_na_categoria(dados.categoria_id, dados.nome)
        secao = Secao(
            categoria_id=dados.categoria_id,
            nome=dados.nome,
            slug=slug,
            posicao=dados.posicao,
        )
        return await self.repo.add(secao)
    
    async def atualiar(self, secao: Secao, dados: SecaoUpdate) -> Secao:
        update = dados.model_dump(exclude_unser=True)

        nova_categoria = update.get("categoria_id", secao.categoria_id)
        if "categoria_id" in update and not await self.cat_repo.get(nova_categoria):
            raise ValueError(f"Categoria {nova_categoria} não existe")
        
        nome_mudou = "nome" in update and update["nome"] != secao.nome
        categoria_mudou = nova_categoria != secao.categoria_id
        if nome_mudou or categoria_mudou:
            nome_final = update.get("nome", secao.nome)
            update["slug"] = await self._slug_unico_na_categoria(
                nova_categoria, nome_final, excluir_id=secao.id
            )
        
        for k, v in update.items():
            setattr(secao, k, v)
        await self.repo.session.flush()
        await self.repo.session.refresh(secao)
        return secao
    
    async def _slug_unico_na_categoria(
            self, categoria_id: int, nome: str, excluir_id: int | None = None
    ) -> str:
        base = slugify(nome)
        slug, n = base, 1
        while True:
            existence = await self.repo.get_by_slug_na_categoria(categoria_id, slug)
            if existence is None or existence.id == excluir_id:
                return slug
            n += 1
            slug = f"{base}-{n}"


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