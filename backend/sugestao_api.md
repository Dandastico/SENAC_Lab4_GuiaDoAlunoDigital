# Sugestão de API — CRUD de Artigos com FastAPI

Documento de recomendações para implementar o CRUD da Base de Conhecimento
(RF03) usando o stack já escolhido em `backend/requirements.txt` e o schema
`cms` definido em `db/schemas/schema_cms.sql`.

> Foco: endpoint de **artigos** (`cms.artigos`). Categorias, seções,
> revisões e visualizações são citadas onde se conectam, mas o detalhamento
> delas pode seguir o mesmo padrão depois.

---

## 1. Visão geral do stack

| Camada | Biblioteca | Papel |
|---|---|---|
| Framework HTTP | `fastapi[standard]` | rotas, OpenAPI, DI |
| Validação | `pydantic` v2 + `pydantic-settings` | schemas de entrada/saída, env vars |
| ORM | `sqlalchemy[asyncio]` 2.0 | modelos e queries async |
| Driver | `asyncpg` | conexão nativa async com Postgres |
| Migrações | `alembic` | versionamento do schema |
| Auth | `pyjwt[crypto]` | validar JWT emitido pelo Supabase |
| Utilidades | `python-slugify` | gerar `slug` a partir do título |

O banco já faz muito trabalho por nós (ENUM de status, `search_vector` via
trigger, `atualizado_em` via trigger, RLS). A API **não** deve duplicar
essas regras — deve confiar nelas e tratar os erros que o banco devolver.

---

## 2. Estrutura de pastas sugerida

Organização por **domínio** (artigos, categorias, etc.), não por tipo de
arquivo. Isso evita que uma feature fique espalhada em 5 pastas diferentes.

```
backend/
├── app/
│   ├── main.py                  # cria FastAPI(), registra routers, middleware
│   ├── config.py                # Settings (BaseSettings) — lê .env
│   ├── db.py                    # engine async, AsyncSession, get_session
│   ├── deps.py                  # dependências comuns (current_user, etc.)
│   ├── security.py              # validação do JWT do Supabase
│   ├── errors.py                # exception handlers
│   └── cms/
│       ├── __init__.py
│       ├── models.py            # SQLAlchemy: Artigo, Categoria, Secao
│       ├── schemas.py           # Pydantic: ArtigoCreate, ArtigoUpdate, ArtigoRead
│       ├── repository.py        # queries (camada de acesso a dados)
│       ├── service.py           # regras de negócio (slug, transições de status)
│       └── router.py            # endpoints /artigos
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py
│   └── cms/
│       └── test_artigos.py
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

**Por que separar `repository`, `service` e `router`?**

- `router` lida só com HTTP (status codes, headers, response models).
- `service` aplica regras de negócio (gerar slug, validar transição de
  status, decidir quando setar `publicado_em`).
- `repository` faz as queries do SQLAlchemy.

Para um CRUD pequeno isso parece overhead, mas evita que `router.py` vire
um arquivo de 800 linhas mais tarde — e torna os testes muito mais simples
(testa o `service` sem subir HTTP).

---

## 3. Configuração e conexão (`app/config.py`, `app/db.py`)

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str           # postgresql+asyncpg://user:pass@host/db
    supabase_jwt_secret: str
    supabase_jwt_audience: str = "authenticated"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
```

```python
# app/db.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

Use `postgresql+asyncpg://...` na `DATABASE_URL` para o SQLAlchemy escolher
o driver async.

---

## 4. Modelo SQLAlchemy (`app/cms/models.py`)

Mapeia 1-para-1 a tabela `cms.artigos`. Como o banco já tem trigger para
`atualizado_em` e `search_vector`, esses campos são **read-only** do lado
da aplicação — deixe o Postgres preencher.

```python
from datetime import datetime
from enum import Enum
from uuid import UUID
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class ArtigoStatus(str, Enum):
    rascunho   = "rascunho"
    publicado  = "publicado"
    escondido  = "escondido"
    agendado   = "agendado"

class Artigo(Base):
    __tablename__ = "artigos"
    __table_args__ = {"schema": "cms"}

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True)
    secao_id:      Mapped[int | None] = mapped_column(ForeignKey("cms.secoes.id"))
    autor_id:      Mapped[UUID | None] = mapped_column(ForeignKey("auth.users.id"))
    titulo:        Mapped[str]      = mapped_column(Text, nullable=False)
    slug:          Mapped[str]      = mapped_column(Text, unique=True, nullable=False)
    conteudo:      Mapped[str]      = mapped_column(Text, nullable=False)
    status:        Mapped[ArtigoStatus] = mapped_column(
        SAEnum(ArtigoStatus, name="artigo_status", schema="cms",
               create_type=False, native_enum=True),
        nullable=False, default=ArtigoStatus.rascunho,
    )
    agendado_para: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicado_em:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em:     Mapped[datetime] = mapped_column(DateTime(timezone=True))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # search_vector: omitido — gerado por trigger, não usado pelo Python
```

**Detalhes importantes:**

- `create_type=False`: o ENUM `cms.artigo_status` já existe no banco; o
  SQLAlchemy não deve tentar criar de novo.
- Omitir `search_vector` no modelo. Se precisar usá-lo em queries
  full-text, faça via `text()` ou função custom.
- `criado_em` e `atualizado_em` sem `server_default` aqui porque o banco
  já define `DEFAULT now()` — basta não passar valor no INSERT.

---

## 5. Schemas Pydantic (`app/cms/schemas.py`)

Separe schemas de **entrada** (Create/Update) dos schemas de **saída**
(Read). Nunca exponha o modelo SQLAlchemy diretamente.

```python
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.cms.models import ArtigoStatus

class ArtigoBase(BaseModel):
    titulo: str = Field(min_length=3, max_length=255)
    conteudo: str = Field(min_length=1)
    secao_id: int | None = None

class ArtigoCreate(ArtigoBase):
    status: ArtigoStatus = ArtigoStatus.rascunho
    agendado_para: datetime | None = None
    # slug NÃO entra aqui — é gerado a partir do título no service

class ArtigoUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=3, max_length=255)
    conteudo: str | None = None
    secao_id: int | None = None
    status: ArtigoStatus | None = None
    agendado_para: datetime | None = None

class ArtigoRead(ArtigoBase):
    id: int
    slug: str
    status: ArtigoStatus
    autor_id: str | None
    agendado_para: datetime | None
    publicado_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime

    model_config = ConfigDict(from_attributes=True)

class ArtigoList(BaseModel):
    items: list[ArtigoRead]
    total: int
    page: int
    page_size: int
```

**Pontos chave:**

- `ArtigoUpdate` tem todos os campos opcionais — PATCH parcial.
- O `slug` não é input; é derivado de `titulo` (`python-slugify`).
- `ArtigoRead` usa `from_attributes=True` (substituto do `orm_mode` do v1)
  para aceitar instâncias do SQLAlchemy.

---

## 6. Repository (`app/cms/repository.py`)

Concentre todas as queries aqui. Os métodos recebem `AsyncSession` por DI.

```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.cms.models import Artigo, ArtigoStatus

class ArtigoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, artigo_id: int) -> Artigo | None:
        return await self.session.get(Artigo, artigo_id)

    async def get_by_slug(self, slug: str) -> Artigo | None:
        stmt = select(Artigo).where(Artigo.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_publicados(self, skip: int, limit: int):
        stmt = (
            select(Artigo)
            .where(Artigo.status == ArtigoStatus.publicado)
            .order_by(Artigo.publicado_em.desc())
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_publicados(self) -> int:
        stmt = select(func.count()).select_from(Artigo).where(
            Artigo.status == ArtigoStatus.publicado
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def add(self, artigo: Artigo) -> Artigo:
        self.session.add(artigo)
        await self.session.flush()       # popula id, criado_em, etc.
        await self.session.refresh(artigo)
        return artigo

    async def delete(self, artigo: Artigo) -> None:
        await self.session.delete(artigo)
```

Use `session.flush()` em vez de `commit()` aqui — o `commit` fica a cargo
do service (ou de um middleware), permitindo agrupar várias operações em
uma única transação.

---

## 7. Service (`app/cms/service.py`)

A camada onde mora a regra de negócio. Aqui é onde **slug** é gerado,
onde transições de **status** são validadas e onde `publicado_em` é setado.

```python
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
            autor_id=autor_id,
        )
        return await self.repo.add(artigo)

    async def atualizar(self, artigo: Artigo, dados: ArtigoUpdate) -> Artigo:
        update = dados.model_dump(exclude_unset=True)
        if "titulo" in update and update["titulo"] != artigo.titulo:
            update["slug"] = await self._slug_unico(update["titulo"])
        # se está publicando agora, marca a data
        if update.get("status") == ArtigoStatus.publicado and not artigo.publicado_em:
            update["publicado_em"] = datetime.now(timezone.utc)
        for k, v in update.items():
            setattr(artigo, k, v)
        await self.repo.session.flush()
        return artigo

    async def _slug_unico(self, titulo: str) -> str:
        base = slugify(titulo)
        slug, n = base, 1
        while await self.repo.get_by_slug(slug):
            n += 1
            slug = f"{base}-{n}"
        return slug
```

**O que o banco já garante** (não duplique em Python):

- `atualizado_em` é atualizado pelo trigger `trg_artigos_atualizado_em`.
- `search_vector` é recalculado pelo trigger `trg_artigos_search_vector`.
- `CHECK (status != 'agendado' OR agendado_para IS NOT NULL)` — se algo
  vier inconsistente, o `IntegrityError` deve virar um `HTTP 422`.

---

## 8. Autenticação JWT do Supabase (`app/security.py`)

Os artigos têm leitura pública mas escrita só para admins. O backend valida
o JWT que o cliente recebeu do Supabase Auth.

```python
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict | None:
    if creds is None:
        return None
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
        )
        return payload    # contém sub (user id), role, etc.
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user is None or user.get("user_metadata", {}).get("funcao") != "admin":
        # alternativa: query em public.perfis para checar funcao
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas admins")
    return user
```

> Ponto a decidir: a `funcao` do usuário fica em `public.perfis.funcao` —
> dá para colocar no `user_metadata` do Supabase (mais simples) ou fazer
> um `SELECT funcao FROM public.perfis WHERE id = sub` (sempre fresco). A
> primeira é mais rápida; a segunda evita JWTs desatualizados após troca
> de funções.

---

## 9. Router (`app/cms/router.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.security import get_current_user, require_admin
from app.cms.repository import ArtigoRepository
from app.cms.service import ArtigoService
from app.cms.schemas import ArtigoCreate, ArtigoUpdate, ArtigoRead, ArtigoList

router = APIRouter(prefix="/artigos", tags=["artigos"])

def _service(session: AsyncSession = Depends(get_session)) -> ArtigoService:
    return ArtigoService(ArtigoRepository(session))

@router.get("", response_model=ArtigoList)
async def listar(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: ArtigoService = Depends(_service),
):
    skip = (page - 1) * page_size
    items = await svc.repo.list_publicados(skip, page_size)
    total = await svc.repo.count_publicados()
    return ArtigoList(items=items, total=total, page=page, page_size=page_size)

@router.get("/{slug}", response_model=ArtigoRead)
async def obter(slug: str, svc: ArtigoService = Depends(_service)):
    artigo = await svc.repo.get_by_slug(slug)
    if not artigo:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return artigo

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
    artigo = await svc.atualizar(artigo, dados)
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
```

**Decisões refletidas no router:**

- `GET /artigos` é **público** (sem dependência de auth) e lista só
  `publicado`. Para um endpoint de admin (que vê rascunhos), considere
  uma rota separada `GET /admin/artigos`.
- `GET /{slug}` em vez de `/{id}` é o que vai bater bonito nas URLs do
  Centro de Ajuda (`/artigos/como-calcular-sua-media`).
- `PATCH` em vez de `PUT` — atualização parcial combina com `ArtigoUpdate`.
- `DELETE` retorna `204`. Pense se vale a pena fazer soft-delete (status
  `escondido`) em vez de delete real — o histórico de revisões e
  visualizações é apagado em cascata pelo `ON DELETE CASCADE`.

---

## 10. `main.py` — montando tudo

```python
from fastapi import FastAPI
from app.cms.router import router as cms_router

app = FastAPI(title="Guia Estudantil FACSENAC-DF — API")
app.include_router(cms_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 11. Migrações com Alembic

O schema já existe em `db/schemas/*.sql` e é a fonte de verdade no
momento. Para alinhar Alembic com isso:

1. `alembic init alembic` na pasta `backend/`.
2. Em `alembic/env.py`, aponte `target_metadata = Base.metadata`.
3. Crie uma **migration inicial vazia** marcando o estado atual:
   `alembic revision --autogenerate -m "baseline"` e revise antes de
   aplicar (ou use `alembic stamp head` se o banco já está montado).
4. A partir daí, toda alteração de schema vira uma migration.

Cuidado: o `autogenerate` do Alembic não detecta triggers, ENUMs ou RLS
— essas coisas precisam ser escritas à mão dentro das migrations
(`op.execute("CREATE TRIGGER ...")`).

---

## 12. Tratamento de erros

Crie handlers globais para os erros mais comuns para não repetir
`try/except` em cada endpoint:

```python
# app/errors.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Conflito de integridade no banco", "info": str(exc.orig)},
    )

# em main.py:
# app.add_exception_handler(IntegrityError, integrity_error_handler)
```

Erros típicos para mapear:

| Exceção | HTTP | Quando ocorre |
|---|---|---|
| `IntegrityError` (unique) | 409 | slug duplicado, etc. |
| `IntegrityError` (check)  | 422 | violação dos CHECKs (status/seção) |
| `ForeignKeyViolation`     | 422 | `secao_id` inexistente |
| `NoResultFound` / `None`  | 404 | artigo não encontrado |
| `jwt.PyJWTError`          | 401 | token inválido/expirado |

---

## 13. Testes

Use `pytest-asyncio` + um Postgres de teste (container) ou um schema
isolado. Estrutura mínima:

```python
# tests/cms/test_artigos.py
import pytest

@pytest.mark.asyncio
async def test_criar_e_obter_artigo(client_admin):
    resp = await client_admin.post("/artigos", json={
        "titulo": "Como calcular sua média",
        "conteudo": "## Passo a passo...",
        "secao_id": 1,
        "status": "publicado",
    })
    assert resp.status_code == 201
    slug = resp.json()["slug"]

    resp = await client_admin.get(f"/artigos/{slug}")
    assert resp.status_code == 200
    assert resp.json()["titulo"] == "Como calcular sua média"
```

Não mocke o banco. Os triggers (`search_vector`, `atualizado_em`) e os
constraints só são exercitados se o teste rodar contra um Postgres de
verdade.

---

## 14. Próximos passos sugeridos

1. **Categorias e seções** — mesmo padrão (model + schemas + repo +
   router), mas só leitura para usuários comuns; CRUD para admin.
2. **Busca full-text** — endpoint `GET /artigos/busca?q=...` usando o
   `search_vector` já indexado:
   ```sql
   WHERE search_vector @@ plainto_tsquery('portuguese', :q)
   ORDER BY ts_rank(search_vector, plainto_tsquery('portuguese', :q)) DESC
   ```
3. **Visualizações** — registrar em `cms.visualizacoes` toda vez que
   `GET /artigos/{slug}` for chamado (preferencialmente em background
   com `BackgroundTasks` para não atrasar a resposta).
4. **Publicação agendada** — um job (cron, ou tabela + worker) que roda
   periodicamente e move artigos com `status='agendado'` e
   `agendado_para <= now()` para `publicado`. Como o índice
   `idx_artigos_agendados` já existe, a query é barata.
5. **Revisões** — gravar uma linha em `cms.revisoes_de_artigos` a cada
   `PATCH` (pode ser feito direto no `service.atualizar`).

---

## 15. Resumo das decisões

- **Confiar no banco**: ENUMs, triggers, CHECKs e RLS não devem ser
  reimplementados em Python.
- **Three-tier por domínio**: `router → service → repository`, agrupados
  em `app/cms/`. Cada camada tem uma responsabilidade clara.
- **Pydantic separado do SQLAlchemy**: nunca expor o modelo do ORM
  direto na resposta.
- **Slug é responsabilidade do service**, não do cliente.
- **Auth via JWT do Supabase**, com dependência `require_admin` para as
  rotas de escrita.
- **Async em todas as camadas** (SQLAlchemy async, asyncpg, endpoints
  `async def`).
