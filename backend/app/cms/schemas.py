# Separa schemas de entrada e saída, não expondo o SQLAlchemy diretamente

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

