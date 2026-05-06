import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings


basic_auth = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(basic_auth)) -> str:
    username_valid = secrets.compare_digest(credentials.username, settings.admin_username)
    password_valid = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (username_valid and password_valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
