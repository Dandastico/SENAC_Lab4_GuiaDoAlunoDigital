# Backend — Guia Estudantil Digital FACSENAC-DF

API REST do Guia Estudantil Digital. Fornece a **base de conhecimento** (artigos
organizados em categorias e seções) e a **autenticação** dos usuários, que é
delegada ao Supabase.

A leitura dos artigos é **pública**; criar, editar e excluir conteúdo exige um
usuário com função `admin`.

---

## Tecnologias

| Ferramenta | Para quê |
|---|---|
| [FastAPI](https://fastapi.tiangolo.com/) | framework web + servidor ASGI (uvicorn) |
| [SQLAlchemy 2 (async)](https://docs.sqlalchemy.org/) + [asyncpg](https://magicstack.github.io/asyncpg/) | acesso ao Postgres de forma assíncrona |
| [Pydantic 2](https://docs.pydantic.dev/) | validação e serialização dos dados |
| [Supabase](https://supabase.com/) | banco de dados Postgres + autenticação (emissão de JWT) |
| [PyJWT](https://pyjwt.readthedocs.io/) | validação do token JWT recebido do Supabase |

---

## Estrutura de pastas

```
backend/
├── app/
│   ├── main.py          # cria o FastAPI e registra as rotas
│   ├── config.py        # lê as variáveis de ambiente (.env)
│   ├── db.py            # conexão e sessão do banco (async)
│   ├── base.py          # Base do SQLAlchemy
│   ├── security.py      # validação de JWT e controle de acesso (admin etc.)
│   ├── errors.py        # tradução de erros do banco em respostas HTTP
│   ├── auth/            # cadastro, login e perfil do usuário
│   └── cms/             # artigos, categorias e seções (base de conhecimento)
├── tests/               # testes automatizados
├── alembic/             # configuração de migrações (ainda sem migrações)
├── requirements.txt     # dependências de produção
├── requirements-dev.txt # dependências de desenvolvimento (testes, lint)
└── .env.example         # modelo das variáveis de ambiente
```

Cada módulo (`auth`, `cms`) segue a mesma divisão:

- **`models.py`** — tabelas do banco (SQLAlchemy)
- **`schemas.py`** — formatos de entrada/saída da API (Pydantic)
- **`repository.py`** — consultas ao banco
- **`service.py`** — regras de negócio
- **`router.py`** — endpoints HTTP

---

## Pré-requisitos

- **Python 3.12 ou superior**
- Acesso a um projeto **Supabase** (banco Postgres + autenticação)
- O schema do banco já criado a partir dos scripts SQL em **`../db/schemas/`**
  (`schema_public.sql`, `schema_cms.sql`, `utils.sql`)

> O Alembic está configurado para migrações futuras, mas no momento **não há
> migrações**: as tabelas são criadas pelos scripts SQL acima, aplicados no Supabase.

---

## Passo a passo para rodar localmente

Todos os comandos são executados **dentro da pasta `backend/`**.

### 1. Criar e ativar um ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows (PowerShell)
```

### 2. Instalar as dependências

```bash
pip install -r requirements.txt
```

Para desenvolver e rodar os testes, instale também as dependências de dev:

```bash
pip install -r requirements-dev.txt
```

### 3. Configurar as variáveis de ambiente

Copie o modelo e preencha com os dados do seu projeto Supabase:

```bash
cp .env.example .env
```

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | URL do Postgres (formato `postgresql+asyncpg://...`) |
| `SUPABASE_URL` | URL base do projeto Supabase |
| `SUPABASE_ANON_KEY` | chave pública (anon) usada nas chamadas de cadastro/login |
| `SUPABASE_JWT_SECRET` | segredo para validar a assinatura do JWT |
| `SUPABASE_JWT_AUDIENCE` | audience esperada no token (normalmente `authenticated`) |
| `SUPABASE_JWT_ISSUER` | issuer esperado no token |

### 4. Subir o servidor local

```bash
uvicorn app.main:app --reload
```

A API ficará disponível em **http://127.0.0.1:8000**.

- Documentação interativa (Swagger): **http://127.0.0.1:8000/docs**
- Verificação de saúde: **http://127.0.0.1:8000/health**

---

## Endpoints principais

> Rotas marcadas com 🔒 exigem o cabeçalho `Authorization: Bearer <token>`.
> As rotas de escrita (criar/editar/excluir) são restritas a usuários `admin`.

### Autenticação — `/auth`
| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/cadastro` | cria a conta no Supabase |
| POST | `/auth/login` | autentica e retorna o JWT + perfil |
| GET | `/auth/me` 🔒 | dados do usuário autenticado |

### Base de conhecimento — `/categorias`, `/secoes`, `/artigos`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/categorias` | lista categorias |
| GET | `/categorias/{slug}` | categoria com suas seções |
| POST / PATCH / DELETE | `/categorias` 🔒 | gerencia categorias (admin) |
| GET | `/secoes?categoria_id=...` | lista seções de uma categoria |
| POST / PATCH / DELETE | `/secoes` 🔒 | gerencia seções (admin) |
| GET | `/artigos` | lista artigos publicados (paginado) |
| GET | `/artigos/{slug}` | exibe um artigo publicado |
| POST / PATCH / DELETE | `/artigos` 🔒 | gerencia artigos (admin) |

---

## Como funciona a autenticação

1. O usuário se cadastra/loga pelas rotas `/auth/*`, que conversam com o Supabase.
2. O Supabase devolve um **JWT**.
3. Nas rotas protegidas, o backend recebe esse token no cabeçalho
   `Authorization: Bearer <token>`, valida a assinatura (`app/security.py`) e
   carrega o perfil do usuário no banco para descobrir sua função
   (`estudante`, `professor` ou `admin`).

---

## Testes e lint

Com as dependências de dev instaladas:

```bash
pytest        # roda os testes
ruff check .  # verifica o estilo do código
```

> Os testes ficam em `tests/`. Alguns dependem de configuração de ambiente/fixtures
> que ainda está em evolução — consulte o módulo antes de rodar.
