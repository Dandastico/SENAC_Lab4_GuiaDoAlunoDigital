from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import Perfil

class PerfilRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID | str) -> Perfil | None:
        return await self.session.get(Perfil, user_id)
    
