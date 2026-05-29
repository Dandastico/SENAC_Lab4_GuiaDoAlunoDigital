from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracoes(BaseSettings):
    database_url: str
    supabase_jwt_secret: str
    supabase_jwt_audience: str
    supabase_jwt_issuer: str
    supabase_url: str
    supabase_anon_key: str

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

configuracoes = Configuracoes()