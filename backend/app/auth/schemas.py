from pydantic import BaseModel, EmailStr, Field
from app.auth.models import PerfilFuncao

class CadastroRequest(BaseModel):
    email: EmailStr
    # regras alinhadas com autenticação do Supabase para senhas
    senha: str = Field(min_length=8, description="Mínimo de 8 caracteres")
    nome_completo: str = Field(min_length=2, max_length=150)

class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

class PerfilRead(BaseModel):
    id: str
    email: str | None
    nome_inteiro: str | None
    funcao: PerfilFuncao

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    perfil: PerfilRead
