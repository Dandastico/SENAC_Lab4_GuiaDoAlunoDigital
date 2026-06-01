import asyncio
import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import configuracoes
from app.auth.repository import PerfilRepository
from app.auth.schemas import CadastroRequest, LoginRequest, TokenResponse, PerfilRead

# timeout para evitar que o Supabase fique lento
SUPABASE_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

def _supabase_headers() -> dict[str, str]:
    # Construído sob demanda (não no import-time) para que rotação da anon_key
    # via recarga das configurações seja refletida sem reinício do processo.
    return {
        "apikey": configuracoes.supabase_anon_key,
        "Content-Type": "application/json",
    }

def _extrair_mensagem_supabase(payload: dict, fallback: str) -> str:
    # dependendo da versão do Supabase, chaves diferentes para tipo de erro
    for chave in ("error_description", "message", "msg", "error"):
        valor = payload.get(chave)
        if isinstance(valor, str) and valor:
            return valor
    return fallback

def _erro_de_rede(exc: Exception) -> HTTPException:
    # converte falhas de comunicação com o Supabase em mensagem clara
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Serviço de autenticação indisponível. Tente novamente em alguns instantes.",
    )

class AuthService:
    def __init__(self, session: AsyncSession):
        self.perfil_repo = PerfilRepository(session)

    async def _post_supabase(self, path: str, json: dict) -> httpx.Response:
        '''Centraliza POST ao Supabase e captura erros de rede'''
        try:
            async with httpx.AsyncClient(timeout=SUPABASE_TIMEOUT) as client:
                return await client.post(
                    f"{configuracoes.supabase_url}{path}",
                    headers=_supabase_headers(),
                    json=json,
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RequestError) as exc:
            raise _erro_de_rede(exc) from exc
        
    async def cadastrar(self, dados: CadastroRequest) -> TokenResponse | None:
        resp = await self._post_supabase(
            "/auth/v1/signup",
            json={
                "email": dados.email,
                "password": dados.senha,
                "data": {"full_name": dados.nome_completo},
            },
        )

        if resp.status_code in (400, 422):
            corpo = resp.json() if resp.content else {}
            error_code = corpo.get("error_code") or corpo.get("code") or ""
            msg = _extrair_mensagem_supabase(corpo, "Erro no cadastro")

            # usuário já existe é o caso mais comum
            if error_code == "user_already_exists" or "already" in msg.lower():
                raise HTTPException(status.HTTP_409_CONFLICT, "Email já cadastrado")
            
            if error_code in ("weak_password", "validation_failed") or resp.status_code == 422:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)
            
            raise HTTPException(status.HTTP_400_BAD_REQUEST, msg)
    
        if resp.status_code >= 500:
            raise _erro_de_rede(Exception("Supabase 5xx"))
        
        resp.raise_for_status()

        dados_supabase = resp.json()

        # se Supabase retorna HTTP 200 mas sem o token
        if not dados_supabase.get("access_token"):
            return None
        
        return await self._montar_token_response(dados_supabase)
    
    async def login(self, dados: LoginRequest) -> TokenResponse:
        resp = await self._post_supabase(
            "/auth/v1/token?grant_type=password",
            json={"email": dados.email, "password": dados.senha},
        )

        # GoTrue pode retornar 400 (invalid_grant, email não confirmado) ou
        # 422 (validação de payload, provedor desativado). Tratamos os dois
        # juntos para evitar cair no resp.raise_for_status() com 500 genérico.
        if resp.status_code in (400, 422):
            corpo = resp.json() if resp.content else {}
            error_code = corpo.get("error_code") or corpo.get("code") or ""
            msg = _extrair_mensagem_supabase(corpo, "")

            if error_code == "email_not_confirmed" or "not confirmed" in msg.lower():
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "E-mail ainda não confirmado. Verifique sua caixa de entrada."
                )

            # 422 com erro fora dos casos acima: provavelmente validação
            # estrutural do payload (provedor desabilitado, formato inválido).
            # Repassa a mensagem do Supabase para o cliente.
            if resp.status_code == 422:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    msg or "Falha na validação do login",
                )

            # 400 sem error_code específico: tratamos como credenciais inválidas
            # sem revelar se foi o e-mail ou a senha que não bateu.
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")

        if resp.status_code >= 500:
            raise _erro_de_rede(Exception("Supabase 5xx"))
        
        resp.raise_for_status()

        dados_supabase = resp.json()
        return await self._montar_token_response(dados_supabase)
    
    async def _montar_token_response(self, dados_supabase: dict) -> TokenResponse:
        '''Consulta perfil no banco e monta a resposta final'''
        # TypeError cobre o caso `dados_supabase["user"]` ser None
        # (e tentar indexar None com ["id"]); KeyError cobre chaves ausentes.
        try:
            user_id = dados_supabase["user"]["id"]
            access_token = dados_supabase["access_token"]
        except (KeyError, TypeError) as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Resposta inválida do serviço de autenticação",
            ) from exc
        
        # `or 3600` cobre tanto chave ausente quanto presente com valor null.
        # dict.get(key, default) só usa o default quando a chave NÃO existe;
        # se Supabase retornar "expires_in": null, .get() devolve None e
        # TokenResponse(expires_in=None) falharia na validação Pydantic.
        expires_in = dados_supabase.get("expires_in") or 3600

        perfil = await self.perfil_repo.get(user_id)
        if perfil is None:
            await asyncio.sleep(0.1)
            perfil = await self.perfil_repo.get(user_id)
        if perfil is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Perfil não encontrado após autenticação",
            )
        
        return TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            perfil=PerfilRead(
                id=str(perfil.id),
                email=dados_supabase["user"].get("email"),
                nome_inteiro=perfil.nome_inteiro,
                funcao=perfil.funcao,
            ),
        )