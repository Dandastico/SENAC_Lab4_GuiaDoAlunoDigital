from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracoes(BaseSettings):
    database_url: str
    supabase_jwt_secret: str
    supabase_jwt_audience: str

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

configuracoes = Configuracoes()