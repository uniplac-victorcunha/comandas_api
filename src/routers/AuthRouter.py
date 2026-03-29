# Victor da Cunha
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from domain.schemas.AuthSchema import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    FuncionarioAuth
)
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.database import get_db
from infra.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token
)
from infra.dependencies import get_current_active_user
from settings import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

router = APIRouter()

@router.post("/auth/login", response_model=TokenResponse, tags=["Autenticação"], status_code=status.HTTP_200_OK)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Autentica o funcionário e retorna tokens JWT"""
    funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.cpf == login_data.cpf).first()
    if not funcionario or not verify_password(login_data.senha, funcionario.senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CPF ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"}
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": funcionario.cpf, "id": funcionario.id, "grupo": funcionario.grupo},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": funcionario.cpf, "id": funcionario.id, "grupo": funcionario.grupo}
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

@router.post("/auth/refresh", response_model=TokenResponse, tags=["Autenticação"], status_code=status.HTTP_200_OK)
async def refresh(refresh_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Renova os tokens JWT usando o refresh token"""
    payload = verify_refresh_token(refresh_data.refresh_token)
    cpf = payload.get("sub")
    funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.cpf == cpf).first()
    if not funcionario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Funcionário não encontrado"
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": funcionario.cpf, "id": funcionario.id, "grupo": funcionario.grupo},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": funcionario.cpf, "id": funcionario.id, "grupo": funcionario.grupo}
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

@router.get("/auth/me", response_model=FuncionarioAuth, tags=["Autenticação"], status_code=status.HTTP_200_OK)
async def me(current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Retorna os dados do funcionário autenticado"""
    return current_user

@router.post("/auth/logout", tags=["Autenticação"], summary="Logout - pública", status_code=status.HTTP_200_OK)
async def logout():
    """Encerra a sessão do funcionário (client-side token invalidation)"""
    return {"message": "Logout realizado com sucesso"}
