from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend import auth

router = APIRouter(prefix="/api/auth", tags=["Accounts"])


class Credentials(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: Credentials):
    """Create an account. Returns {"token", "user"}."""
    try:
        return auth.register(body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(body: Credentials):
    """Log in. Returns {"token", "user"}."""
    try:
        return auth.login(body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
def logout(authorization: Optional[str] = Header(default=None)):
    token = auth.bearer_token(authorization)
    if token:
        auth.logout(token)
    return {"success": True}


@router.get("/me")
def me(authorization: Optional[str] = Header(default=None)):
    """The logged-in user, or 401."""
    user = auth.user_for_token(auth.bearer_token(authorization))
    if not user and auth.AUTH_REQUIRED:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return {"user": user, "authRequired": auth.AUTH_REQUIRED}
