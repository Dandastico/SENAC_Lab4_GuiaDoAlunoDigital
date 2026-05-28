# Sugestão de API — Autenticação e Perfis de Usuário

Documento companheiro de `sugestao_api.md` e `sugestao_api_categorias_secoes.md`.
Cobre o módulo de autenticação: cadastro, login, perfil do usuário logado e controle
de acesso baseado na `funcao` definida em `public.perfis`.

> O banco já faz boa parte do trabalho: o trigger `trg_criar_perfil_apos_registro`
> cria uma linha em `public.perfis` automaticamente a cada novo `auth.users`. O
> backend só precisa chamar a API do Supabase Auth para criar o usuário e depois
> emitir/validar JWTs.

---

## 1. Visão geral do fluxo

```
Cliente                     FastAPI backend              Supabase
  |                               |                          |
  |-- POST /auth/cadastro ------->|                          |
  |   {email, senha, nome}        |-- POST /auth/v1/signup ->|
  |                               |                          |-- INSERT auth.users
  |                               |                          |-- trigger cria perfil
  |                               |<-- {access_token, ...} --|
  |<-- {access_token, funcao} ----|                          |
  |                               |                          |
  |-- POST /auth/login ---------->|                          |
  |   {email, senha}              |-- POST /auth/v1/token  ->|
  |                               |<-- {access_token, ...} --|
  |<-- {access_token, funcao} ----|-- SELECT perfis WHERE id=sub
  |                               |                          |
  |-- GET /artigos (+ Bearer) --->|                          |
  |                               |-- valida JWT (pyjwt)     |
  |                               |-- SELECT perfis WHERE id=sub
  |<-- 200 artigos publicados ----|                          |
  |                               |                          |
  |-- POST /artigos (+ Bearer) -->|                          |
  |   (requer funcao='admin')     |-- valida JWT             |
  |                               |-- verifica perfil.funcao |
  |<-- 201 / 403 -----------------|                          |
```

**Responsabilidades:**

| Quem | O quê |
|---|---|
| Supabase Auth | Criar usuário, validar senha, emitir JWT, refresh token |
| Trigger `trg_criar_perfil_apos_registro` | Criar `public.perfis` automaticamente no signup |
| FastAPI | Proxy do signup/login, validar JWT, checar `funcao` do perfil |
| `public.perfis.funcao` | Fonte de verdade do nível de acesso (`estudante`, `professor`, `admin`) |

---

## 2. Configuração

### `app/config.py` — adicionar duas variáveis

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracoes(BaseSettings):
    database_url: str
    supabase_jwt_secret: str
    supabase_jwt_audience: str
    supabase_url: str        # ex.: https://xyzxyz.supabase.co
    supabase_anon_key: str   # chave pública anon do projeto Supabase

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

configuracoes = Configuracoes()
```

### `.env.example` — acrescentar

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:senha@db.xyzxyz.supabase.co:5432/postgres
SUPABASE_JWT_SECRET=sua-jwt-secret-aqui
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_URL=https://xyzxyz.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Onde encontrar cada valor no painel Supabase:
- `SUPABASE_URL` e `SUPABASE_ANON_KEY` → **Project Settings → API**
- `SUPABASE_JWT_SECRET` → **Project Settings → API → JWT Settings → JWT Secret**

---

## 3. Modelo SQLAlchemy — `public.perfis`

`Perfil` pertence ao domínio de autenticação, não ao CMS. Crie `app/auth/models.py`
separado de `app/cms/models.py`.

Como os dois arquivos de modelos precisam compartilhar a mesma instância de
`Base` (caso contrário o Alembic não enxerga todos os modelos juntos), extraia
o `Base` para um módulo neutro:

```python
# app/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

Atualize `app/cms/models.py` para importar desse novo arquivo:

```python
# app/cms/models.py — trocar a declaração local pelo import compartilhado
from app.base import Base   # ← substituir o "class Base(DeclarativeBase): pass" existente
```

Crie `app/auth/models.py`:

```python
# app/auth/models.py

from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID
from sqlalchemy import Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.base import Base


class PerfilFuncao(str, PyEnum):
    estudante = "estudante"
    professor = "professor"
    admin     = "admin"


class Perfil(Base):
    __tablename__ = "perfis"
    __table_args__ = {"schema": "public"}

    # Não use ForeignKey("auth.users.id") aqui.
    # O schema `auth` é interno do Supabase e não está no Base.metadata;
    # declarar o FK quebraria o `alembic revision --autogenerate` (tabela não encontrada).
    # A constraint já existe no banco — o SQLAlchemy não precisa dela para funcionar.
    id:            Mapped[UUID]         = mapped_column(primary_key=True)
    nome_inteiro:  Mapped[str | None]   = mapped_column(Text)
    funcao:        Mapped[PerfilFuncao] = mapped_column(
        SAEnum(PerfilFuncao, name="perfil_funcao", schema="public",
               create_type=False, native_enum=True),
        nullable=False,
        default=PerfilFuncao.estudante,
    )
    criado_em:     Mapped[datetime]     = mapped_column(DateTime(timezone=True))
    atualizado_em: Mapped[datetime]     = mapped_column(DateTime(timezone=True))
```

**Detalhes:**

- `create_type=False` — o ENUM `public.perfil_funcao` já existe no banco.
- Não declare `server_default` para `criado_em` / `atualizado_em` — o banco
  tem `DEFAULT now()` e o trigger `trg_perfis_atualizado_em` cuida das atualizações.
- `nome_inteiro` é preenchido pelo trigger a partir de `raw_user_meta_data->>'full_name'`,
  então não é necessário fazê-lo manualmente no INSERT.

**`alembic/env.py`** — garanta que ambos os módulos de modelos sejam importados
antes de passar `target_metadata`, para que o Alembic registre todas as tabelas:

```python
# alembic/env.py
from app.base import Base
import app.auth.models   # registra Perfil no Base.metadata
import app.cms.models    # registra Artigo, Categoria, Secao no Base.metadata

target_metadata = Base.metadata
```

---

## 4. Schemas Pydantic

Crie `app/auth/schemas.py` (ou acrescente em `app/cms/schemas.py`).

```python
# app/auth/schemas.py

from pydantic import BaseModel, EmailStr, Field
from app.auth.models import PerfilFuncao


class CadastroRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=6, description="Mínimo 6 caracteres")
    nome_completo: str = Field(min_length=2, max_length=150)


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class PerfilRead(BaseModel):
    id: str
    email: str | None   # vem de payload.get("email") — pode ser None em OAuth/magic-link
    nome_inteiro: str | None
    funcao: PerfilFuncao


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    perfil: PerfilRead
```

**Decisões:**

- `CadastroRequest.nome_completo` é enviado como `user_metadata.full_name` ao
  Supabase. O trigger `trg_criar_perfil_apos_registro` lê exatamente esse campo
  para preencher `perfis.nome_inteiro`.
- `TokenResponse` embute `PerfilRead` para evitar uma segunda chamada do
  frontend logo após o login.
- `PerfilRead.id` é `str` (UUID serializado) para simplicidade do JSON.

---

## 5. Repository — `PerfilRepository`

```python
# app/auth/repository.py

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import Perfil, PerfilFuncao


class PerfilRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID | str) -> Perfil | None:
        return await self.session.get(Perfil, user_id)

    async def get_funcao(self, user_id: UUID | str) -> PerfilFuncao | None:
        """Retorna apenas a funcao — evita carregar o objeto inteiro em hot paths."""
        stmt = select(Perfil.funcao).where(Perfil.id == str(user_id))
        return (await self.session.execute(stmt)).scalar_one_or_none()
```

---

## 6. Service — `AuthService`

Usa `httpx.AsyncClient` (já no `requirements.txt`) para chamar a API REST do
Supabase Auth. Não há senha armazenada no banco da aplicação — o Supabase cuida
disso.

```python
# app/auth/service.py

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import configuracoes
from app.auth.repository import PerfilRepository
from app.auth.schemas import CadastroRequest, LoginRequest, TokenResponse, PerfilRead


SUPABASE_HEADERS = {
    "apikey": configuracoes.supabase_anon_key,
    "Content-Type": "application/json",
}


class AuthService:
    def __init__(self, session: AsyncSession):
        self.perfil_repo = PerfilRepository(session)

    async def cadastrar(self, dados: CadastroRequest) -> TokenResponse | None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{configuracoes.supabase_url}/auth/v1/signup",
                headers=SUPABASE_HEADERS,
                json={
                    "email": dados.email,
                    "password": dados.senha,
                    "data": {"full_name": dados.nome_completo},
                    # "data" vira raw_user_meta_data no Supabase,
                    # que o trigger usa para preencher perfis.nome_inteiro
                },
            )

        if resp.status_code == 400:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, resp.json().get("msg", "Erro no cadastro"))
        if resp.status_code == 422:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "E-mail inválido ou senha muito fraca")
        resp.raise_for_status()

        dados_supabase = resp.json()

        # Quando confirmação de e-mail está ativada (padrão em produção), Supabase retorna
        # HTTP 200 mas com access_token=null. Retornamos None para que o router emita um
        # JSONResponse(202) estruturado. Usar HTTPException(202) serializaria o corpo como
        # {"detail": "..."} — formato de erro — para um fluxo que é bem-sucedido.
        if not dados_supabase.get("access_token"):
            return None

        return await self._montar_token_response(dados_supabase)

    async def login(self, dados: LoginRequest) -> TokenResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{configuracoes.supabase_url}/auth/v1/token?grant_type=password",
                headers=SUPABASE_HEADERS,
                json={"email": dados.email, "password": dados.senha},
            )

        if resp.status_code == 400:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")
        resp.raise_for_status()

        dados_supabase = resp.json()
        return await self._montar_token_response(dados_supabase)

    async def _montar_token_response(self, dados_supabase: dict) -> TokenResponse:
        """Consulta o perfil no banco e monta a resposta final."""
        user_id = dados_supabase["user"]["id"]
        access_token = dados_supabase["access_token"]
        # `or 3600` cobre dois casos: chave ausente E chave presente com valor null.
        # dict.get(key, default) só usa o default quando a chave não existe;
        # se Supabase retornar "expires_in": null, .get() devolve None e
        # TokenResponse(expires_in=None) falharia na validação Pydantic.
        expires_in = dados_supabase.get("expires_in") or 3600

        perfil = await self.perfil_repo.get(user_id)
        if perfil is None:
            # O trigger ainda não rodou (improvável) ou o perfil foi deletado.
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Perfil não encontrado")

        return TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            perfil=PerfilRead(
                id=str(perfil.id),
                email=dados_supabase["user"].get("email"),  # .get() — email ausente em OAuth
                nome_inteiro=perfil.nome_inteiro,
                funcao=perfil.funcao,
            ),
        )
```

**Por que não usar `supabase-py`?**

A biblioteca oficial `supabase-py` funciona bem, mas adiciona uma dependência pesada
(e às vezes conflita com versões de `httpx` e `gotrue-py`). Como só precisamos de
dois endpoints da API REST do Supabase, `httpx` direto é mais simples e previsível.
Se o projeto crescer e precisar de Storage, Realtime ou RPC do Supabase, vale
revisitar essa decisão.

---

## 7. `security.py` — corrigir verificação de `funcao`

O `security.py` atual lê a `funcao` de `user_metadata`, que **o próprio usuário pode
alterar** via SDK do Supabase. Qualquer usuário poderia se autopromover a admin.
A fonte de verdade é `public.perfis.funcao`, que só é alterada pelo servidor.

```python
# app/security.py — versão corrigida

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import configuracoes
from app.db import get_sessao
from app.auth.repository import PerfilRepository
from app.auth.models import PerfilFuncao

bearer = HTTPBearer(auto_error=False)


def _decodificar_jwt(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            configuracoes.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=configuracoes.supabase_jwt_audience,
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict | None:
    """
    Valida o JWT e retorna o payload. Não consulta o banco.
    Use esta dependência em rotas públicas que apenas identificam
    o usuário opcionalmente (ex.: registrar visualização).
    """
    if creds is None:
        return None
    return _decodificar_jwt(creds.credentials)


async def get_usuario_autenticado(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    sessao: AsyncSession = Depends(get_sessao),
) -> dict:
    """
    Valida o JWT e carrega o perfil do banco.
    Retorna dict com chaves: sub, email, funcao, nome_inteiro.
    Use esta dependência em rotas que precisam da funcao do usuário.
    """
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token não fornecido")

    payload = _decodificar_jwt(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        # JWT válido mas sem claim "sub" — token malformado, não é erro de perfil.
        # Sem esta guarda, session.get(Perfil, None) emitiria WHERE id = NULL e
        # retornaria 404 "Perfil não encontrado" — código e mensagem incorretos.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido: campo 'sub' ausente")

    perfil = await PerfilRepository(sessao).get(user_id)
    if perfil is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado")

    return {
        "sub": user_id,
        "email": payload.get("email"),
        "funcao": perfil.funcao,
        "nome_inteiro": perfil.nome_inteiro,
    }


async def require_autenticado(
    usuario: dict = Depends(get_usuario_autenticado),
) -> dict:
    """Exige qualquer usuário autenticado (estudante, professor ou admin)."""
    return usuario


async def require_professor_ou_admin(
    usuario: dict = Depends(get_usuario_autenticado),
) -> dict:
    """Exige funcao professor ou admin."""
    if usuario["funcao"] not in (PerfilFuncao.professor, PerfilFuncao.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a professores e admins")
    return usuario


async def require_admin(
    usuario: dict = Depends(get_usuario_autenticado),
) -> dict:
    """Exige funcao admin. Substitui a versão anterior que lia user_metadata."""
    if usuario["funcao"] != PerfilFuncao.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas admins")
    return usuario
```

**Impacto nas rotas existentes:** os endpoints que já usam `Depends(require_admin)`
continuam funcionando sem alteração de assinatura. A única mudança é que agora a
`funcao` vem do banco (`public.perfis`) em vez do JWT — o que é mais seguro e
sempre atualizado.

**Custo:** uma query extra por requisição protegida (busca por PK UUID —
milissegundos). Se isso virar gargalo, use um cache em memória (ex.: `cachetools`)
com TTL curto (30–60 s).

---

## 8. Router — `auth_router`

```python
# app/auth/router.py

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
    responses={202: {"description": "E-mail de confirmação enviado; faça login após confirmar."}},
)
async def cadastrar(
    dados: CadastroRequest,
    svc: AuthService = Depends(_service),
):
    """
    Cria conta no Supabase Auth e retorna o JWT + perfil (HTTP 201).
    O trigger do banco cria public.perfis automaticamente com funcao='estudante'.
    Quando confirmação de e-mail está ativada no Supabase, retorna HTTP 202 com mensagem
    em vez de token — o cliente deve aguardar a confirmação antes de fazer login.
    """
    resultado = await svc.cadastrar(dados)
    if resultado is None:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"message": "Conta criada. Confirme o e-mail recebido antes de fazer login."},
        )
    return resultado


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    dados: LoginRequest,
    svc: AuthService = Depends(_service),
):
    """Autentica e retorna o JWT + perfil."""
    return await svc.login(dados)


@auth_router.get("/me", response_model=PerfilRead)
async def perfil_atual(
    usuario: dict = Depends(get_usuario_autenticado),
):
    """Retorna os dados do usuário autenticado. Útil para o frontend verificar a funcao."""
    return PerfilRead(
        id=usuario["sub"],
        email=usuario["email"],
        nome_inteiro=usuario["nome_inteiro"],
        funcao=usuario["funcao"],
    )
```

**Decisão sobre refresh token:**

O Supabase retorna também um `refresh_token` no login. Este documento não o expõe
na resposta do FastAPI intencionalmente — o refresh deve ser feito pelo cliente
diretamente contra o Supabase (`POST /auth/v1/token?grant_type=refresh_token`),
sem precisar passar pelo backend. Se você quiser centralizar esse fluxo, adicione:

```python
# Adicionar ao topo de app/auth/router.py:
# from pydantic import BaseModel   ← necessário para RefreshRequest

class RefreshRequest(BaseModel):
    refresh_token: str

@auth_router.post("/refresh", response_model=TokenResponse)
async def renovar_token(dados: RefreshRequest, svc: AuthService = Depends(_service)):
    return await svc.renovar(dados.refresh_token)

# Em AuthService.renovar:
async def renovar(self, refresh_token: str) -> TokenResponse:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{configuracoes.supabase_url}/auth/v1/token?grant_type=refresh_token",
            headers=SUPABASE_HEADERS,
            json={"refresh_token": refresh_token},
        )
    if resp.status_code == 400:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido ou expirado")
    resp.raise_for_status()
    return await self._montar_token_response(resp.json())
```

---

## 9. Estrutura de pastas sugerida

```
backend/app/
├── main.py
├── config.py
├── db.py
├── base.py              ← Base (DeclarativeBase) compartilhado entre domínios
├── security.py          ← atualizado (ver §7)
├── errors.py
├── auth/
│   ├── __init__.py
│   ├── models.py        ← PerfilFuncao, Perfil  (schema: public)
│   ├── schemas.py       ← CadastroRequest, LoginRequest, TokenResponse, PerfilRead
│   ├── repository.py    ← PerfilRepository
│   ├── service.py       ← AuthService (chama Supabase REST)
│   └── router.py        ← auth_router (/auth/cadastro, /auth/login, /auth/me)
└── cms/
    ├── models.py        ← ArtigoStatus, Artigo, Categoria, Secao  (schema: cms)
    ├── schemas.py
    ├── repository.py
    ├── service.py
    └── router.py
```

---

## 10. `main.py` — registrar o router

```python
from fastapi import FastAPI
from app.cms.router import router as artigos_router, categorias_router, secoes_router
from app.auth.router import auth_router
from sqlalchemy.exc import IntegrityError
from app.errors import integrity_error_handler

app = FastAPI(title="Guia Estudantil FACSENAC-DF – API")

app.include_router(auth_router)
app.include_router(categorias_router)
app.include_router(secoes_router)
app.include_router(artigos_router)

app.add_exception_handler(IntegrityError, integrity_error_handler)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 11. Promover usuário a admin

Novos cadastros sempre recebem `funcao = 'estudante'` (default do banco). Não há
endpoint público para mudar a própria `funcao` — isso é intencional e necessário
para a segurança do sistema.

**Opção A — query direta (recomendado para configuração inicial):**

```sql
UPDATE public.perfis
SET funcao = 'admin'
WHERE id = '<uuid-do-usuario>';
```

Execute no SQL Editor do Supabase. Seguro porque requer acesso ao painel do projeto.

**Opção B — endpoint admin protegido:**

Se precisar promover usuários pela própria API (ex.: um painel administrativo),
crie um endpoint separado acessível apenas por admins já existentes:

```python
# Em app/auth/router.py — adicionar/completar os imports do §8 com:
# from fastapi import APIRouter, Depends, HTTPException, Path, status
# from pydantic import BaseModel
# from app.security import get_usuario_autenticado, require_admin
# from app.auth.repository import PerfilRepository
# from app.auth.models import PerfilFuncao

class AlterarFuncaoRequest(BaseModel):
    funcao: PerfilFuncao

@auth_router.patch("/perfis/{user_id}/funcao", response_model=PerfilRead)
async def alterar_funcao(
    dados: AlterarFuncaoRequest,       # body sem default — deve vir ANTES de params com default
    user_id: str = Path(...),
    admin: dict = Depends(require_admin),
    sessao: AsyncSession = Depends(get_sessao),
):
    repo = PerfilRepository(sessao)
    perfil = await repo.get(user_id)
    if not perfil:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    perfil.funcao = dados.funcao
    await sessao.flush()
    await sessao.refresh(perfil)
    # Capturar os valores ANTES do commit. Com expire_on_commit=True (padrão do
    # SQLAlchemy), os atributos expiram após commit e qualquer acesso em contexto
    # async lança MissingGreenlet. O db.py deste projeto usa expire_on_commit=False,
    # mas capturar aqui torna o código seguro independente dessa configuração.
    perfil_id   = str(perfil.id)
    nome        = perfil.nome_inteiro
    funcao      = perfil.funcao
    await sessao.commit()
    return PerfilRead(
        id=perfil_id,
        email=None,        # email fica em auth.users, inacessível via SQLAlchemy
        nome_inteiro=nome,
        funcao=funcao,
    )
```

---

## 12. Resumo dos endpoints

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| `POST` | `/auth/cadastro` | Pública | Cria conta e retorna JWT |
| `POST` | `/auth/login` | Pública | Autentica e retorna JWT |
| `GET` | `/auth/me` | Bearer (qualquer funcao) | Retorna perfil do usuário logado |
| `POST` | `/auth/refresh` | Bearer (refresh token) | Renova o JWT (opcional) |
| `PATCH` | `/auth/perfis/{id}/funcao` | Bearer (admin) | Promove/rebaixa funcao |

---

## 13. Mapeamento de `funcao` por rota do CMS

Com as dependências do `security.py` atualizado, aplique assim nas rotas existentes:

| Rota | Dependência sugerida |
|---|---|
| `GET /artigos` | Pública — sem dependência |
| `GET /artigos/{slug}` | Pública — sem dependência |
| `POST /artigos` | `require_admin` |
| `PATCH /artigos/{id}` | `require_admin` |
| `DELETE /artigos/{id}` | `require_admin` |
| `GET /categorias` | Pública |
| `GET /categorias/{slug}` | Pública |
| `POST /categorias` | `require_admin` |
| `PATCH /categorias/{id}` | `require_admin` |
| `DELETE /categorias/{id}` | `require_admin` |
| `GET /secoes` | Pública |
| `POST /secoes` | `require_admin` |
| `PATCH /secoes/{id}` | `require_admin` |
| `DELETE /secoes/{id}` | `require_admin` |

Se no futuro `professor` puder criar rascunhos, substitua `require_admin` por
`require_professor_ou_admin` nos endpoints de criação e edição — sem mudar
mais nada no código.

---

## 14. Pontos de atenção

- **E-mail de confirmação**: por padrão o Supabase exige confirmação de e-mail
  antes de aceitar login. Para desenvolvimento, desative em
  **Authentication → Providers → Email → Confirm email**.
- **CORS**: se o frontend for um domínio diferente do backend, configure:
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["https://seusite.com"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Expiração do JWT**: o token do Supabase expira em 1 hora por padrão.
  Configure em **Authentication → JWT expiry** e instrua o frontend a usar o
  `refresh_token` antes do vencimento.
- **RLS em `public.perfis`**: atualmente não há RLS na tabela de perfis
  (`schema_public.sql` não declara políticas). Se você expor `perfis` via
  PostgREST/Supabase diretamente (não pela API FastAPI), adicione políticas
  para que cada usuário só leia/escreva o próprio perfil.
- **`email` não está em `public.perfis`**: o e-mail fica em `auth.users`, que
  o backend não acessa diretamente pelo SQLAlchemy (é schema interno do Supabase).
  O e-mail disponível nos endpoints vem do payload JWT (`payload["email"]`).
