# Sugestão de API — CRUD de Categorias e Seções com FastAPI

Documento companheiro de `sugestao_api.md`. Foca nas duas entidades
"estruturais" da Base de Conhecimento: `cms.categorias` (segmentação de
mais alto nível) e `cms.secoes` (subdivisões dentro de cada categoria).
Pressupõe que o leitor já passou pelo documento de artigos — o stack,
estrutura de pastas, configuração (`app/config.py`, `app/db.py`),
autenticação (`app/security.py`), tratamento de erros (`app/errors.py`)
e padrão de migrações são exatamente os mesmos.

---

## 1. Por que tratar essas duas entidades juntas

Categorias e seções formam uma **árvore de dois níveis** — toda seção
pertence a uma categoria, todo artigo pertence a uma seção. O CRUD é mais
simples que o de artigos (sem workflow de status, sem `search_vector`,
sem `atualizado_em`), mas a relação hierárquica entre eles cria três
pontos que merecem atenção:

1. **Escopo do `slug`**: globalmente único para categorias, único **por
   categoria** para seções.
2. **Comportamento de `DELETE`**: `cms.secoes.categoria_id` é
   `ON DELETE CASCADE` e `cms.artigos.secao_id` é `ON DELETE RESTRICT`
   — combinando os dois, **apagar uma categoria que tem artigos vai
   falhar** (a cascata tenta apagar as seções e o RESTRICT dos artigos
   barra). A API precisa traduzir esse erro pro cliente.
3. **Ordenação no menu**: ambas têm `posicao SMALLINT` para o frontend
   ordenar — então listar quase sempre é `ORDER BY posicao, nome`.

Faz sentido organizar como um **único pacote** dentro do CMS, em vez de
dois pacotes separados — eles compartilham repository helpers (lookup
por slug, validação de cascata) e mudam quase sempre juntos.

---

## 2. Onde colocar o código

Tudo continua dentro de `app/cms/`. Sugestão de divisão dos arquivos:

```
app/cms/
├── __init__.py
├── models.py            # Artigo, Categoria, Secao  (já existe)
├── schemas.py           # acrescentar Categoria*/Secao* aos existentes
├── repository.py        # acrescentar CategoriaRepository, SecaoRepository
├── service.py           # acrescentar CategoriaService, SecaoService
└── router.py            # acrescentar routers /categorias e /secoes
```

Não vale a pena dividir em `cms/categorias/` e `cms/secoes/` agora —
são poucas linhas por arquivo, e a duplicação de imports vira o maior
custo. Quando algum desses módulos passar de ~200 linhas, aí sim vale
dividir.

---

## 3. Modelo SQLAlchemy

As classes `Categoria` e `Secao` **já existem** em `app/cms/models.py`,
mapeadas 1-para-1 com o schema. Não precisa mexer. Apenas reproduzo
aqui pra referência:

```python
class Categoria(Base):
    __tablename__ = "categorias"
    __table_args__ = {"schema": "cms"}

    id:        Mapped[int]        = mapped_column(Integer, primary_key=True)
    nome:      Mapped[str]        = mapped_column(Text, nullable=False)
    slug:      Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    posicao:   Mapped[int]        = mapped_column(SmallInteger, nullable=False, default=0)
    criado_em: Mapped[datetime]   = mapped_column(DateTime(timezone=True))

class Secao(Base):
    __tablename__ = "secoes"
    __table_args__ = (
        UniqueConstraint("categoria_id", "slug", name="uq_secoes_categoria_slug"),
        {"schema": "cms"},
    )

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True)
    categoria_id: Mapped[int]      = mapped_column(
        ForeignKey("cms.categorias.id", ondelete="CASCADE"), nullable=False,
    )
    nome:         Mapped[str]      = mapped_column(Text, nullable=False)
    slug:         Mapped[str]      = mapped_column(Text, nullable=False)
    posicao:      Mapped[int]      = mapped_column(SmallInteger, nullable=False, default=0)
    criado_em:    Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

**O que vale notar:**

- Nenhuma das duas tem `atualizado_em` — o schema não declara, então
  o `PATCH` não vai retornar timestamp de modificação. Se isso for
  necessário no futuro, exige migration + trigger (como o `trg_artigos_atualizado_em`).
- `criado_em` é preenchido por `DEFAULT now()` no banco — não declare
  `server_default=` na coluna SQLAlchemy; é só não passar valor no INSERT.
- Não há `relationship()` aqui. Se quiser navegar de `Categoria` para
  suas `secoes` em Python (ex.: pra montar uma resposta aninhada),
  adicione `secoes: Mapped[list["Secao"]] = relationship(back_populates="categoria")`
  e o par em `Secao`. Mas só faça isso quando for usar — `selectinload`
  é necessário no fetch async, senão estoura `MissingGreenlet`.

---

## 4. Schemas Pydantic

Acrescente em `app/cms/schemas.py`. Mesmo padrão dos artigos: Base /
Create / Update / Read / List.

```python
# ===== Categoria =====

class CategoriaBase(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    descricao: str | None = None
    posicao: int = Field(default=0, ge=0)

class CategoriaCreate(CategoriaBase):
    pass  # slug é gerado pelo service

class CategoriaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    descricao: str | None = None
    posicao: int | None = Field(default=None, ge=0)

class CategoriaRead(CategoriaBase):
    id: int
    slug: str
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)

# ===== Secao =====

class SecaoBase(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    posicao: int = Field(default=0, ge=0)

class SecaoCreate(SecaoBase):
    categoria_id: int     # obrigatório no POST

class SecaoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    posicao: int | None = Field(default=None, ge=0)
    categoria_id: int | None = None   # permite mover seção entre categorias

class SecaoRead(SecaoBase):
    id: int
    categoria_id: int
    slug: str
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)

# ===== Variantes aninhadas =====
# Útil pra um endpoint tipo GET /categorias/{slug}/arvore que devolve
# a categoria com suas seções pré-carregadas, em uma única chamada.

class CategoriaComSecoes(CategoriaRead):
    secoes: list[SecaoRead] = []
```

**Decisões:**

- `slug` não entra em Create/Update — é derivado de `nome` no service,
  pelo mesmo motivo dos artigos.
- `CategoriaUpdate` e `SecaoUpdate` têm todos os campos opcionais —
  PATCH parcial.
- `SecaoUpdate.categoria_id` é opcional **e permitido**. Mover uma seção
  entre categorias é uma operação válida; só lembre que o slug precisa
  ser revalidado pra unicidade no novo escopo.
- `posicao: int = Field(ge=0)` impede valores negativos no input —
  o banco aceitaria, mas semanticamente não faz sentido.

---

## 5. Repository

Mesma estrutura do `ArtigoRepository`. Cada classe recebe uma
`AsyncSession` por DI e concentra as queries.

```python
# app/cms/repository.py — acrescentar

from sqlalchemy import select, func
from app.cms.models import Categoria, Secao

class CategoriaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, categoria_id: int) -> Categoria | None:
        return await self.session.get(Categoria, categoria_id)

    async def get_by_slug(self, slug: str) -> Categoria | None:
        stmt = select(Categoria).where(Categoria.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def listar(self, skip: int, limit: int) -> list[Categoria]:
        stmt = (
            select(Categoria)
            .order_by(Categoria.posicao, Categoria.nome)
            .offset(skip).limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def contar(self) -> int:
        stmt = select(func.count()).select_from(Categoria)
        return (await self.session.execute(stmt)).scalar_one()

    async def add(self, categoria: Categoria) -> Categoria:
        self.session.add(categoria)
        await self.session.flush()
        await self.session.refresh(categoria)
        return categoria

    async def delete(self, categoria: Categoria) -> None:
        await self.session.delete(categoria)


class SecaoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, secao_id: int) -> Secao | None:
        return await self.session.get(Secao, secao_id)

    async def get_by_slug_na_categoria(
        self, categoria_id: int, slug: str
    ) -> Secao | None:
        stmt = select(Secao).where(
            Secao.categoria_id == categoria_id,
            Secao.slug == slug,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def listar_da_categoria(self, categoria_id: int) -> list[Secao]:
        stmt = (
            select(Secao)
            .where(Secao.categoria_id == categoria_id)
            .order_by(Secao.posicao, Secao.nome)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def add(self, secao: Secao) -> Secao:
        self.session.add(secao)
        await self.session.flush()
        await self.session.refresh(secao)
        return secao

    async def delete(self, secao: Secao) -> None:
        await self.session.delete(secao)
```

**Pontos a notar:**

- `get_by_slug_na_categoria` recebe o **par** `(categoria_id, slug)`
  porque a unicidade do slug de seção é escopada por categoria. Buscar
  só por slug seria ambíguo.
- `listar_da_categoria` não pagina por padrão — categorias raramente
  têm dezenas de seções; se chegar a precisar, segue o mesmo padrão
  de `list_publicados` dos artigos.
- Como nos artigos, `flush()` em vez de `commit()` aqui: o commit fica
  com o router (uma transação por requisição HTTP).

---

## 6. Service

A regra de negócio principal é a **geração de slug único** — com o
detalhe de que para seção o escopo é a categoria, não o banco inteiro.

```python
# app/cms/service.py — acrescentar

from slugify import slugify
from app.cms.models import Categoria, Secao
from app.cms.schemas import CategoriaCreate, CategoriaUpdate, SecaoCreate, SecaoUpdate
from app.cms.repository import CategoriaRepository, SecaoRepository

class CategoriaService:
    def __init__(self, repo: CategoriaRepository):
        self.repo = repo

    async def criar(self, dados: CategoriaCreate) -> Categoria:
        slug = await self._slug_unico(dados.nome)
        categoria = Categoria(
            nome=dados.nome,
            slug=slug,
            descricao=dados.descricao,
            posicao=dados.posicao,
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
        await self.repo.session.flush()
        await self.repo.session.refresh(categoria)
        return categoria

    async def _slug_unico(self, nome: str, excluir_id: int | None = None) -> str:
        base = slugify(nome)
        slug, n = base, 1
        while True:
            existente = await self.repo.get_by_slug(slug)
            if existente is None or existente.id == excluir_id:
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

    async def atualizar(self, secao: Secao, dados: SecaoUpdate) -> Secao:
        update = dados.model_dump(exclude_unset=True)

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
            existente = await self.repo.get_by_slug_na_categoria(categoria_id, slug)
            if existente is None or existente.id == excluir_id:
                return slug
            n += 1
            slug = f"{base}-{n}"
```

**O que o banco já garante** (não duplique em Python):

- `cms.categorias.slug UNIQUE` — slug duplicado de categoria volta como
  `IntegrityError` → 409 pelo handler global.
- `cms.secoes UNIQUE (categoria_id, slug)` — idem para seções dentro
  da mesma categoria.
- `cms.secoes.categoria_id ON DELETE CASCADE` — apagar uma categoria
  apaga suas seções automaticamente (mas veja a próxima seção sobre
  o efeito colateral com artigos).

**Detalhe importante** sobre `_slug_unico` com `excluir_id`: ao **editar**
uma categoria/seção, o `get_by_slug` encontraria o próprio registro
sendo editado e adicionaria sufixo `-2` sem necessidade. Passar o id
atual em `excluir_id` resolve isso. (No documento de artigos esse
mesmo bug existe no `_slug_unico` original — vale corrigir lá também.)

---

## 7. Tratamento do `DELETE` em cascata

Esse é o ponto onde a hierarquia morde. Considere o cenário:

```
Categoria "Acadêmico" (id=1)
├── Seção "Matrícula" (id=10)
│   └── Artigo "Como se matricular" (referencia secao_id=10)
└── Seção "Avaliações" (id=11)
```

Se o admin tentar `DELETE /categorias/1`:

1. O `ON DELETE CASCADE` de `cms.secoes.categoria_id` quer apagar as
   seções 10 e 11.
2. O `ON DELETE RESTRICT` de `cms.artigos.secao_id` barra a remoção
   da seção 10 (tem artigo dependente).
3. Postgres aborta toda a transação e levanta `ForeignKeyViolationError`.

Esse comportamento é **correto** (não dá pra deixar artigos órfãos
silenciosamente), mas a mensagem padrão do Postgres é hostil. Duas
abordagens:

**Abordagem A — confiar no handler global de IntegrityError.**
O `errors.py` já mapeia `ForeignKeyViolationError` para 422. O cliente
recebe 422 com a mensagem do Postgres. Simples, mas o erro é genérico.

**Abordagem B — checar antes e devolver erro amigável.**
No `CategoriaService.deletar`, conte artigos vinculados antes de
tentar apagar:

```python
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
```

Recomendo a **Abordagem B** pra `DELETE /categorias` e a **A** pra
`DELETE /secoes` (a mensagem do Postgres é menos opaca quando o
relacionamento é direto). A escolha real depende de quanto polimento
você quer dar pra UX do admin.

---

## 8. Router

```python
# app/cms/router.py — acrescentar

from fastapi import APIRouter, Depends, HTTPException, Query, status

# ===== Categorias =====

categorias_router = APIRouter(prefix="/categorias", tags=["categorias"])

def _categoria_service(session: AsyncSession = Depends(get_sessao)) -> CategoriaService:
    return CategoriaService(CategoriaRepository(session))

@categorias_router.get("", response_model=list[CategoriaRead])
async def listar_categorias(svc: CategoriaService = Depends(_categoria_service)):
    return await svc.repo.listar(skip=0, limit=100)

@categorias_router.get("/{slug}", response_model=CategoriaComSecoes)
async def obter_categoria(
    slug: str,
    svc: CategoriaService = Depends(_categoria_service),
    secao_repo_dep: AsyncSession = Depends(get_sessao),
):
    categoria = await svc.repo.get_by_slug(slug)
    if not categoria:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    secao_repo = SecaoRepository(svc.repo.session)
    secoes = await secao_repo.listar_da_categoria(categoria.id)
    return CategoriaComSecoes(
        **CategoriaRead.model_validate(categoria).model_dump(),
        secoes=[SecaoRead.model_validate(s) for s in secoes],
    )

@categorias_router.post("", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED)
async def criar_categoria(
    dados: CategoriaCreate,
    admin = Depends(require_admin),
    svc: CategoriaService = Depends(_categoria_service),
):
    categoria = await svc.criar(dados)
    await svc.repo.session.commit()
    return categoria

@categorias_router.patch("/{categoria_id}", response_model=CategoriaRead)
async def atualizar_categoria(
    categoria_id: int,
    dados: CategoriaUpdate,
    admin = Depends(require_admin),
    svc: CategoriaService = Depends(_categoria_service),
):
    categoria = await svc.repo.get(categoria_id)
    if not categoria:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    categoria = await svc.atualizar(categoria, dados)
    await svc.repo.session.commit()
    return categoria

@categorias_router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_categoria(
    categoria_id: int,
    admin = Depends(require_admin),
    svc: CategoriaService = Depends(_categoria_service),
):
    categoria = await svc.repo.get(categoria_id)
    if not categoria:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await svc.deletar(categoria)   # checa artigos vinculados — ver §7
    await svc.repo.session.commit()

# ===== Seções =====

secoes_router = APIRouter(prefix="/secoes", tags=["secoes"])

def _secao_service(session: AsyncSession = Depends(get_sessao)) -> SecaoService:
    return SecaoService(SecaoRepository(session), CategoriaRepository(session))

@secoes_router.get("", response_model=list[SecaoRead])
async def listar_secoes(
    categoria_id: int = Query(..., description="Filtrar por categoria"),
    svc: SecaoService = Depends(_secao_service),
):
    return await svc.repo.listar_da_categoria(categoria_id)

@secoes_router.post("", response_model=SecaoRead, status_code=status.HTTP_201_CREATED)
async def criar_secao(
    dados: SecaoCreate,
    admin = Depends(require_admin),
    svc: SecaoService = Depends(_secao_service),
):
    try:
        secao = await svc.criar(dados)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
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
    # se houver artigos vinculados, o RESTRICT levanta IntegrityError
    # e o handler global devolve 422 — comportamento aceitável aqui
    await svc.repo.session.commit()
```

**Decisões refletidas no router:**

- **Dois routers separados** (`categorias_router` e `secoes_router`) com
  prefixos distintos, em vez de aninhar `/categorias/{id}/secoes`. A
  rota aninhada é mais "REST puro", mas duplica handlers (você acaba
  precisando de `/secoes/{id}` mesmo assim pra PATCH/DELETE). Manter
  flat com filtro `?categoria_id=` é mais simples.
- **`GET /categorias/{slug}`** devolve a categoria **com suas seções
  embutidas** — economiza uma round-trip pro frontend montar a árvore
  do menu. Use `CategoriaComSecoes` como response model.
- **`GET /secoes` exige `categoria_id`** (`Query(...)` sem default). Listar
  todas as seções globalmente raramente é útil; quando for, é só
  remover a obrigatoriedade.
- **`DELETE /categorias` chama `svc.deletar`** (checagem amigável de
  artigos vinculados); **`DELETE /secoes` chama `repo.delete` direto**
  e deixa o RESTRICT do banco se virar. Coerente com §7.
- Os `try/except ValueError → HTTPException 422` nos endpoints de
  seção são pra capturar o "categoria não existe" levantado pelo
  service. Uma alternativa mais limpa é criar uma exceção customizada
  (`CategoriaNaoEncontrada`) e registrar um exception handler global —
  mas pra duas ocorrências, o `try/except` resolve sem overhead.

---

## 9. `main.py` — registrar os routers

```python
from app.cms.router import (
    router as artigos_router,
    categorias_router,
    secoes_router,
)

app.include_router(artigos_router)
app.include_router(categorias_router)
app.include_router(secoes_router)
```

O `integrity_error_handler` já registrado cobre os erros de UNIQUE
e FK das duas novas entidades — não precisa de handler novo.

---

## 10. Pontos de atenção / armadilhas

- **RLS não está habilitado** nas tabelas `categorias` e `secoes` (só
  em `artigos`). Isso significa que, se alguém conectar direto no
  Postgres com um JWT de usuário comum (via PostgREST/Supabase),
  consegue ler e escrever. Pra API que estamos construindo isso é
  irrelevante (a autorização é feita no `require_admin`), mas se você
  for expor essas tabelas pelo PostgREST do Supabase, adicione policies
  parecidas com as de artigos.
- **`posicao` tem comportamento sutil**: não há restrição de unicidade,
  então duas categorias podem ter `posicao=0`. O frontend que decide
  o desempate (provavelmente por `nome` alfabético, como o repository
  faz). Se você precisar de uma ordem totalmente determinística, mude
  pra `ARRAY` ou faça `UNIQUE` em `posicao`.
- **Mover seção entre categorias** muda o slug porque o escopo mudou —
  o que invalida URLs externas que apontavam pra seção antiga. Se isso
  for um problema, registre o slug antigo numa tabela de redirects ou
  evite permitir essa operação pela API.
- **Cache do frontend** vai querer invalidar quando uma categoria muda
  posição. Como não tem `atualizado_em`, o frontend precisa refetchar
  baseado em outro sinal (versão da resposta inteira, ETag, etc.).

---

## 11. Próximos passos sugeridos

1. **Reordenação em lote** — endpoint `PATCH /categorias/posicoes` que
   recebe `[{id: 1, posicao: 0}, {id: 2, posicao: 1}, ...]` para o
   admin reorganizar o menu numa tacada só.
2. **Endpoint de árvore completa** — `GET /cms/arvore` que devolve
   `[Categoria(secoes=[Secao(...), ...]), ...]` em uma única chamada.
   Útil pra o menu lateral do site.
3. **Soft-delete opcional** — se "categoria sem artigos" virar comum
   mas você quiser preservar histórico, adicione `ativo: bool = True`
   e filtre na listagem em vez de apagar.
4. **Validação de `posicao` única por nível** — se isso passar a
   importar, vire constraint no banco (`UNIQUE (posicao)` em
   `categorias`; `UNIQUE (categoria_id, posicao)` em `secoes`).

---

## 12. Resumo das decisões

- **Reusa toda a infra dos artigos**: config, db, security, errors,
  router style, three-tier por domínio.
- **Slug escopado**: globalmente único para categoria, único-por-categoria
  para seção — refletido em `get_by_slug` vs `get_by_slug_na_categoria`.
- **Hierarquia respeitada nas deleções**: `DELETE /categorias` checa
  artigos vinculados antes; `DELETE /secoes` deixa o RESTRICT do banco
  responder.
- **Routers separados, sem nesting de URL** — `?categoria_id=` filtra
  seções, e `GET /categorias/{slug}` pode devolver seções embutidas
  pra evitar round-trips do frontend.
- **Sem `atualizado_em`** — o schema não declara; aceite isso ou
  adicione via migration + trigger se virar necessário.
