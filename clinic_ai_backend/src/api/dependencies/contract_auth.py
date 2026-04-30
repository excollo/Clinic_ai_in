from typing import Optional

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from src.core.config import get_settings

async def require_contract_auth(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_doctor_id: Optional[str] = Header(None, alias="X-Doctor-ID"),
):
    if not x_api_key or not x_doctor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing auth headers",
        )
    settings = get_settings()
    try:
        payload = jwt.decode(
            x_api_key,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("doctor_id") != x_doctor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token mismatch")
        return {"doctor_id": x_doctor_id}
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
