# mapeia de 1-para-1 o modelo do banco de dados

from datetime import datetime
from enum import Enum
from uuid import UUID
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class ArtigoStatus(str, Enum):
    rascunho = "rascunho"
    publicado = "publicado"
    escondido = "escondido"
    programado = "programado"

class Artigo(Base):
    __tablename__ = "artigos"
    __table_args__ = {"schema": "cms"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secao_id: Mapped[int | None] = mapped_column(ForeignKey("cms.sessoes.id"))
    autor_id: Mapped[UUID | None] = mapped_column(ForeignKey("auth.users.id"))
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    conteudo = Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ArtigoStatus] = mapped_column(
        SAEnum(ArtigoStatus, name="artigos_status", schema="cms",
               created_type=False, native_enum=True),
               nullable=False,
               default=ArtigoStatus.rascunho
    )
    agendado_para: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))