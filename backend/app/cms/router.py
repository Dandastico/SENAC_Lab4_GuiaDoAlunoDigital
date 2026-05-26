from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_sessao
from app.security import require_admin
from app.cms.repository import ArtigoRepository
from app.cms.service import ArtigoService
from app.cms.schemas import ArtigoCreate, ArtigoUpdate, ArtigoRead, ArtigoList

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