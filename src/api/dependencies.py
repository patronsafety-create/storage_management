from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError

from src.infrastructure.database import get_db
from src.infrastructure.security import SECRET_KEY, ALGORITHM
from src.domain_model import auth_models, auth_schemas

# این خط به Swagger می‌گوید فرم لاگین باید اطلاعات را به کدام آدرس بفرستد
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    این تابع به عنوان گارد امنیتی عمل می‌کند.
    توکن را می‌خواند، صحت امضای آن را چک می‌کند و کاربر متصل به آن را از دیتابیس استخراج می‌کند.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="اعتبارنامه‌های شما معتبر نیست یا منقضی شده است",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # رمزگشایی توکن با کلید مخفی سرور
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = auth_schemas.TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    
    # بررسی وجود کاربر در سیستم
    user = db.query(auth_models.User).filter(auth_models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
        
    return user