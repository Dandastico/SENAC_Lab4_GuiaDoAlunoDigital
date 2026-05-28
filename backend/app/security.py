import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import configuracoes

bearer = HTTPBearer(auto_error=False)

async def get_current_user(
        creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict | None:
    if creds is None:
        return None
    try:
        payload = jwt.decode(
            creds.credentials,
            configuracoes.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=configuracoes.supabase_jwt_audience,
        )
        return payload
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))
    
async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user is None or user.get("app_metadata", {}).get("funcao") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas admins")
    return user