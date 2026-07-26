from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from core.config import settings, validate_password
from core.rate_limit import limiter
from core.security import TokenData, create_access_token, verify_token
from core.database import (
    get_user_by_username,
    hash_password,
    verify_password,
    create_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest) -> dict[str, str]:
    if not req.username or not req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )
    pw_error = validate_password(req.password)
    if pw_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_error)
    hashed = hash_password(req.password)
    success = create_user(req.username, hashed, role="learner")
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists"
        )
    return {"status": "ok", "message": "User registered successfully"}


@router.post("/token")
@limiter.limit("10/minute")
def login(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends()
) -> dict[str, str]:
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
def read_current_user(
    token_data: TokenData = Depends(verify_token),
) -> dict[str, str | None]:
    return {"username": token_data.username, "role": token_data.role}
