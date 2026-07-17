from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from core.config import settings
from core.security import TokenData, create_access_token, verify_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict[str, str]:
    # Placeholder: Replace with real user/password lookup and hashing.
    if form_data.username != "learner" or form_data.password != "secret":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(
        data={"sub": form_data.username, "role": "learner"},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
def read_current_user(token_data: TokenData = Depends(verify_token)) -> dict[str, str | None]:
    return {"username": token_data.username, "role": token_data.role}
