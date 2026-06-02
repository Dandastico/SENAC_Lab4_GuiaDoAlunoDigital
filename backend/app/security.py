import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import configuracoes
from app.db import get_sessao
from app.auth.repository import PerfilRepository
from app.auth.models import PerfilFuncao

bearer = HTTPBearer(auto_error=False)

# Supabase moderno assina os JWT com chaves assimétricas (ES256) e expõe as
# chaves públicas via JWKS. O cliente faz cache das chaves entre requisições.
_jwks_client = PyJWKClient(
    f"{configuracoes.supabase_url}/auth/v1/.well-known/jwks.json",
    cache_keys=True,
)

def _decodificar_jwt(token: str) -> dict:
    '''
    Valida assinatura + audience + issuer + expiração.
    Validar 'iss' impede token assinado por outro projeto Supabase.

    Escolhe o caminho de validação pelo header 'alg' do token:
    - HS256: segredo simétrico legado (supabase_jwt_secret)
    - ES256/RS256: chave pública obtida via JWKS
    '''
    opcoes = dict(
        audience=configuracoes.supabase_jwt_audience,
        issuer=configuracoes.supabase_jwt_issuer,
    )

    alg = jwt.get_unverified_header(token).get("alg")

    if alg == "HS256":
        return jwt.decode(
            token,
            configuracoes.supabase_jwt_secret,
            algorithms=["HS256"],
            **opcoes,
        )

    chave_assinatura = _jwks_client.get_signing_key_from_jwt(token).key
    return jwt.decode(
        token,
        chave_assinatura,
        algorithms=["ES256", "RS256"],
        **opcoes,
    )


async def get_current_user(
        creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict | None:
    '''
    Dependência opcional para rotas públicas
    '''
    if creds is None:
        return None
    try:
        return _decodificar_jwt(creds.credentials)
    except jwt.PyJWTError:
        return None


async def get_usuario_autenticado(
        creds: HTTPAuthorizationCredentials | None = Depends(bearer),
        sessao: AsyncSession = Depends(get_sessao),
) -> dict:
    '''
    valida JWT, carrega perfil do BD e retorna dict com:
    sub, email, funcao, nome_inteiro
    '''
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado")
    
    try:
        payload = _decodificar_jwt(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado")
    except jwt.InvalidAudienceError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token com audience inválida")
    except jwt.InvalidIssuerError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de issuer inválido")
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {e}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido: campo 'sub' ausente")
    
    perfil = await PerfilRepository(sessao).get(user_id)
    if perfil is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado")
    
    return {
        "sub": user_id,
        "email": payload.get("email"),
        "funcao": perfil.funcao,
        "nome_inteiro": perfil.nome_inteiro
    }


async def require_autenticado(
        usuario: dict = Depends(get_usuario_autenticado),
) -> dict:
    '''Exige qualquer usuário autenticado (estudante, professor ou admin)'''
    return usuario


async def require_professor_ou_admin(
        usuario: dict = Depends(get_usuario_autenticado),
) -> dict:
    funcao = PerfilFuncao(usuario["funcao"])
    if funcao not in (PerfilFuncao.professor, PerfilFuncao.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito aos professores e admins")
    return usuario


async def require_admin(usuario: dict = Depends(get_usuario_autenticado)) -> dict:
    if PerfilFuncao(usuario["funcao"]) != PerfilFuncao.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a admins")
    return usuario