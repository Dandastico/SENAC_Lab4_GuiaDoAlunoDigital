from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_sessao
from app.security import require_admin
from app.cms.repository import ArtigoRepository, CategoriaRepository, SecaoRepository
from app.cms.service import ArtigoService, CategoriaService, SecaoService
from app.cms.schemas import ArtigoCreate, ArtigoUpdate, ArtigoRead, ArtigoList
from app.cms.schemas import CategoriaCreate, CategoriaUpdate, CategoriaRead, CategoriaComSecoes
from app.cms.schemas import SecaoCreate, SecaoUpdate, SecaoRead

# ===== Artigos =====

router = APIRouter(prefix="/artigos", tags=["artigos"])

def _service(session: AsyncSession = Depends(get_sessao)) -> ArtigoService:
    return ArtigoService(ArtigoRepository(session))

@router.get("", response_model=ArtigoList)
async def listar(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: ArtigoService = Depends(_service)
):
    skip = (page - 1) * page_size
    items = await svc.repo.list_publicados(skip, page_size)
    total = await svc.repo.count_publicados()
    return ArtigoList(items=items, total=total, page=page, page_size=page_size)

@router.post("", response_model=ArtigoRead, status_code=status.HTTP_201_CREATED)
async def criar(
    dados: ArtigoCreate,
    admin = Depends(require_admin),
    svc: ArtigoService = Depends(_service),
):
    artigo = await svc.criar(dados, autor_id=admin["sub"])
    await svc.repo.session.commit()
    return artigo

@router.patch("/{artigo_id}", response_model=ArtigoRead)
async def atualizar(
    artigo_id: int,
    dados: ArtigoUpdate,
    admin = Depends(require_admin),
    svc: ArtigoService = Depends(_service),
):
    artigo = await svc.repo.get(artigo_id)
    if not artigo:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    artigo = await svc.atualizar(artigo,dados)
    await svc.repo.session.commit()
    return artigo

@router.delete("/{artigo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir(
    artigo_id: int,
    admin = Depends(require_admin),
    svc: ArtigoService = Depends(_service),
):
    artigo = await svc.repo.get(artigo_id)
    if not artigo:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await svc.repo.delete(artigo)
    await svc.repo.session.commit()


# ===== Categorias =====

categorias_router = APIRouter(prefix="/categorias", tags=["categorias"])

def _categoria_service(session: AsyncSession = Depends(get_sessao)) -> CategoriaService:
    return CategoriaService(CategoriaRepository(session))

@categorias_router.get("", response_model=list[CategoriaRead])
async def lista_categorias(svc: CategoriaService = Depends(_categoria_service)):
    return await svc.repo.listar(skip=0, limit=100)

@categorias_router.get("/{slug}", response_model=CategoriaComSecoes)
async def obter_categoria(
    slug: str,
    svc: CategoriaService = Depends(_categoria_service),
    secao_repo_dep: AsyncSession = Depends(get_sessao)
):
    categoria = await svc.repo.get_by_slug(slug)
    if not categoria:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    secao_repo = SecaoRepository(svc.repo.session)
    secoes = await svc.repo.listar_da_categoria(categoria.id)
    return CategoriaComSecoes(
        **CategoriaRead.model_validate(categoria).model_dump,
        secoes=[SecaoRead.model_validate(s) for s in secoes]
    )

@categorias_router.post(
    response_model=CategoriaRead,
    status_code=status.HTTP_201_CREATED)
async def criar_categoria(
    dados: CategoriaCreate,
    admin = Depends(require_admin),
    svc: CategoriaService = Depends(_categoria_service)
):
    categoria = await svc.criar(dados)
    await svc.repo.session.commit()
    return categoria

@categorias_router.patch(
    "/{categoria_id}",
    response_model=CategoriaRead)
async def atualizar_categoria(
    categoria_id: int,
    dados: CategoriaUpdate,
    admin = Depends(require_admin),
    svc: CategoriaService = Depends(_categoria_service)
):
    categoria  = await svc.repo.get(categoria_id)
    if not categoria:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    categoria = await svc.atualizar(categoria, dados)
    await svc.repo.session.commit()
    return categoria

@categorias_router.delete(
    "/{categoria_id}",
    status_code=status.HTTP_204_NO_CONTENT)
async def excluit_categoria(
    categoria_id: int,
    admin = Depends(require_admin),
    svc: CategoriaService = Depends(_categoria_service)
):
    categoria = await svc.repo.get(categoria_id)
    if not categoria:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await svc.deletar(categoria)
    await svc.repo.session.commit()

# ===== Seções =====

secoes_router = APIRouter(prefix="/secoes", tags=["secoes"])

def _secao_service(session: AsyncSession = Depends(get_sessao)) -> SecaoService:
    return SecaoService(SecaoRepository(session), CategoriaRepository(session))

@secoes_router.get("", response_model=list[SecaoRead])
async def listar_secoes(
    categoria_id: int = Query(..., description="Filtrar por categoria"),
    svc: SecaoService = Depends(_secao_service)
):
    return await svc.listar_da_categoria(categoria_id)

@secoes_router.post("", response_model=SecaoRead, status_code=status.HTTP_201_CREATED)
async def criar_secao(
    dados: SecaoCreate,
    admin = Depends(require_admin),
    svc: SecaoService = Depends(_secao_service),
):
    try:
        secao = await svc.criar(dados)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    await svc.repo.session.commit()
    return secao

@secoes_router.patch("/{secao_id}", response_model=SecaoRead)
async def atualizar_secao(
    secao_id: int,
    dados: SecaoUpdate,
    admin = Depends(require_admin),
    svc: SecaoService = Depends(_secao_service),
):
    secao = await svc.repo.get(secao_id)
    if not secao:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        secao = await svc.atualizar(secao, dados)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    await svc.repo.session.commit()
    return secao

@secoes_router.delete("/{secao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_secao(
    secao_id: int,
    admin = Depends(require_admin),
    svc: SecaoService = Depends(_secao_service),
):
    secao = await svc.repo.get(secao_id)
    if not secao:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await svc.repo.delete(secao)
    await svc.repo.session.commit()

    