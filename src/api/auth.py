from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db
from src.infrastructure import security
from src.domain_model import auth_models, auth_schemas

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=auth_schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    بررسی نام کاربری و رمز عبور. 
    در صورت صحت، یک توکن JWT برای دسترسی به سیستم صادر می‌شود.
    """
    user = db.query(auth_models.User).filter(auth_models.User.username == form_data.username).first()
    
    # اگر کاربر نبود یا پسورد هش‌شده با پسورد ورودی تطابق نداشت
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور اشتباه است",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="این حساب کاربری غیرفعال شده است")

    # تولید توکن با شناسه (sub) برابر با نام کاربری
    access_token = security.create_access_token(
        data={"sub": user.username}, 
        expires_delta=timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}