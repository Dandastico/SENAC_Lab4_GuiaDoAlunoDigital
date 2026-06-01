# representa 1-para-1 tabelas no banco de dados

from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID
from sqlalchemy import Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.base import Base

class PerfilFuncao(str, PyEnum):
    estudante = "estudante"
    professor = "professor"
    admin = "admin"

class Perfil(Base):
    __tablename__ = "perfis"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(primary_key=True)
    nome_inteiro: Mapped[str | None] = mapped_column(Text)
    funcao: Mapped[PerfilFuncao] = mapped_column(
        SAEnum(PerfilFuncao, name="perfil_funcao", schema="public",
               create_type=False, native_enum=True),
               nullable=False,
               default=PerfilFuncao.estudante,
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


