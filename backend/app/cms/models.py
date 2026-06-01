# mapeia de 1-para-1 o modelo do banco de dados

from datetime import datetime
from enum import Enum
from uuid import UUID
from sqlalchemy import Text, Integer, SmallInteger, DateTime, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.base import Base

# ------------------ Artigos ------------------

class ArtigoStatus(str, Enum):
    rascunho = "rascunho"
    publicado = "publicado"
    escondido = "escondido"
    agendado = "agendado"

class Artigo(Base):
    __tablename__ = "artigos"
    __table_args__ = {"schema": "cms"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secao_id: Mapped[int | None] = mapped_column(ForeignKey("cms.secoes.id"))
    # Não declaramos ForeignKey("auth.users.id"): o schema `auth` é interno do
    # Supabase e não pertence ao Base.metadata, então declará-lo aqui quebraria
    # `alembic revision --autogenerate`. A constraint já existe no banco
    # (definida em db/schemas/schema_cms.sql).
    autor_id: Mapped[UUID | None] = mapped_column()
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ArtigoStatus] = mapped_column(
        SAEnum(ArtigoStatus, name="artigo_status", schema="cms",
               create_type=False, native_enum=True),
               nullable=False,
               default=ArtigoStatus.rascunho
    )
    agendado_para: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))

# ------------------ Categoria ------------------
class Categoria(Base):
    __tablename__ = "categorias"
    __table_args__ = {"schema": "cms"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    posicao: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))

# ------------------ Secao ------------------
class Secao(Base):
    __tablename__ = "secoes"
    __table_args__ = (
        UniqueConstraint("categoria_id", "slug", name="uq_secoes_categoria_slug"),
        {"schema": "cms"}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoria_id: Mapped[int] = mapped_column(
        ForeignKey("cms.categorias.id", ondelete="CASCADE"),
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    posicao: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))