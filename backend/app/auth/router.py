from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_sessao
from app.security import get_usuario_autenticado
from app.auth.service import AuthService
from app.auth.schemas import CadastroRequest, LoginRequest, TokenResponse, PerfilRead

auth_router = APIRouter(prefix="/auth", tags=["auth"])

def _service(sessao: AsyncSession = Depends(get_sessao)) -> AuthService:
    return AuthService(sessao)

@auth_router.post(
    "/cadastro",
    response_model=TokenResponse,
    status_code=201,
    responses={202: {"description": "E-mail de confirmação enviado; faça login após confirmar"}},
)
async def cadastrar(
    dados: CadastroRequest,
    svc: AuthService = Depends(_service),
):
    """
    Cria conta no Supabase Auth e retorna o JWT com perfil.
    """
    resultado = await svc.cadastrar(dados)
    if resultado is None:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"message": "Conta criada. Confirme o e-mail recebido antes de fazer o login."},
        )
    return resultado

@auth_router.post("/login", response_model=TokenResponse)
async def login(
    dados: LoginRequest,
    svc: AuthService = Depends(_service),
):
    '''Autentica e retorna JWT com perfil'''
    return await svc.login(dados)

@auth_router.get("/me", response_model=PerfilRead)
async def perfil_atual(
    usuario: dict = Depends(get_usuario_autenticado),
):
    '''Retorna dados do usuário autenticado. Frontend verifica a função do usuário'''
    return PerfilRead(
        id=usuario["sub"],
        email=usuario["email"],
        nome_inteiro=usuario["nome_inteiro"],
        funcao=usuario["funcao"],
    )