# Separa schemas de entrada e saída, não expondo o SQLAlchemy diretamente

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.cms.models import ArtigoStatus

# ===== Artigos =====

class ArtigoBase(BaseModel):
    titulo: str = Field(min_length=3, max_length=255)
    conteudo: str = Field(min_length=1)
    secao_id: int | None = None

class ArtigoCreate(ArtigoBase):
    status: ArtigoStatus = ArtigoStatus.rascunho
    agendado_para: datetime | None = None

    @model_validator(mode="after")
    def agendado_exige_data(self):
        if self.status == ArtigoStatus.agendado and self.agendado_para is None:
            raise ValueError("agendado_para é obrigatório quando status é 'agendado'")
        return self

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

# ===== Categorias =====

class CategoriaBase(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    descricao: str | None = None
    posicao: int = Field(default=0, ge=0)

class CategoriaCreate(CategoriaBase):
    pass # slug gerado pelo service.py

class CategoriaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    descricao: str | None = None
    posicao: int | None = Field(default=None, ge=0)

class CategoriaRead(CategoriaBase):
    id: int
    slug: str
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)

# ===== Seção =====

class SecaoBase(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    posicao: int = Field(default=0, ge=0)

class SecaoCreate(SecaoBase):
    categoria_id: int # obrigatório

class SecaoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    posicao: int | None = Field(default=None, ge=0)
    categoria_id: int | None = None # pode mover seção entre categorias

class SecaoRead(SecaoBase):
    id: int
    categoria_id: int
    slug: str
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)

# ===== Variantes aninhadas =====

class CategoriaComSecoes(CategoriaRead):
    # carrega seções pré-carregadas de uma categoria
    secoes: list[SecaoRead] = []