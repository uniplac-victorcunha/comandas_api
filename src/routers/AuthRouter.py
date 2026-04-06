# Victor da Cunha
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi.errors import RateLimitExceeded

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
from infra.rate_limit import limiter, get_rate_limit
from settings import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from services.AuditoriaService import AuditoriaService

router = APIRouter()

@router.post("/auth/login", response_model=TokenResponse, tags=["Autenticação"], summary="Login de funcionário - pública - retorna access e refresh token")
@limiter.limit(get_rate_limit("critical"))
async def login(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Realiza login do funcionário e retorna access token e refresh token
    - **cpf**: CPF do funcionário
    - **senha**: Senha do funcionário

    Retorna:
    - access_token: Token de curta duração
    - refresh_token: Token de longa duração
    """
    try:
        # Busca funcionário pelo CPF
        funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.cpf == login_data.cpf).first()
        if not funcionario:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CPF ou senha inválidos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Verifica se a senha está correta
        if not verify_password(login_data.senha, funcionario.senha):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CPF ou senha inválidos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Cria o access token JWT (curta duração)
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": funcionario.cpf,
                "id": funcionario.id,
                "grupo": funcionario.grupo
            },
            expires_delta=access_token_expires
        )
        # Cria o refresh token JWT (longa duração)
        refresh_token = create_refresh_token(
            data={
                "sub": funcionario.cpf,
                "id": funcionario.id,
                "grupo": funcionario.grupo
            }
        )
        # Registrar auditoria de login
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=funcionario.id,
            acao="LOGIN",
            recurso="AUTH",
            request=request
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao realizar login: {str(e)}")

@router.post("/auth/refresh", response_model=TokenResponse, tags=["Autenticação"], summary="Refresh token - pública - renova access token")
@limiter.limit(get_rate_limit("critical"))
async def refresh(request: Request, refresh_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Renova os tokens JWT usando o refresh token"""
    try:
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
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao renovar token: {str(e)}")

@router.get("/auth/me", response_model=FuncionarioAuth, tags=["Autenticação"], status_code=status.HTTP_200_OK, summary="Dados do usuário atual - protegida por JWT")
@limiter.limit(get_rate_limit("moderate"))
async def me(request: Request, current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Retorna os dados do funcionário autenticado"""
    return current_user

@router.post("/auth/logout", tags=["Autenticação"], summary="Logout - pública", status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("critical"))
async def logout(request: Request, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Encerra a sessão do funcionário (client-side token invalidation)"""
    try:
        # Registrar auditoria de logout
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="LOGOUT",
            recurso="AUTH",
            request=request
        )
        return {"message": "Logout realizado com sucesso"}
    except RateLimitExceeded:
        raise
    except Exception as e:
        return {"message": "Logout realizado com sucesso"}
