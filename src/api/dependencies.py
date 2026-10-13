"""
api/dependencies.py — احراز هویت Bearer Token برای Swagger UI
برای محافظت از روترهای HTML از core/dependencies.py استفاده کنید.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from src.infrastructure.database import get_db
from src.infrastructure.security import SECRET_KEY, ALGORITHM
from src.domain_model.auth_schemas import TokenData
from src.domain_model.auth_models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user_bearer(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """احراز هویت Bearer Token — برای Swagger UI و API clients"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="اعتبارنامه‌های شما معتبر نیست یا منقضی شده است",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user