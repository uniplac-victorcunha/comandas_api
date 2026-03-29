# Victor da Cunha
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from infra.database import get_db
from infra.security import verify_access_token
from infra.orm.FuncionarioModel import FuncionarioDB
from domain.schemas.AuthSchema import FuncionarioAuth

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> FuncionarioAuth:
    payload = verify_access_token(credentials.credentials)
    cpf: str = payload.get("sub")
    id_funcionario: int = payload.get("id")
    if cpf is None or id_funcionario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido - dados incompletos",
            headers={"WWW-Authenticate": "Bearer"}
        )
    funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.id == id_funcionario).first()
    if not funcionario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Funcionário não encontrado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if funcionario.cpf != cpf:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido - CPF não corresponde",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return FuncionarioAuth(id=funcionario.id, nome=funcionario.nome, matricula=funcionario.matricula, cpf=funcionario.cpf, grupo=funcionario.grupo)

def get_current_active_user(current_user: FuncionarioAuth = Depends(get_current_user)) -> FuncionarioAuth:
    return current_user

def require_group(group_required: list[int] = None):
    def check_group(current_user: FuncionarioAuth = Depends(get_current_active_user)) -> FuncionarioAuth:
        if group_required is None:
            return current_user
        if current_user.grupo not in group_required:
            groups_str = ", ".join(map(str, group_required))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão negada - requerido um dos grupos: {groups_str}"
            )
        return current_user
    return check_group
