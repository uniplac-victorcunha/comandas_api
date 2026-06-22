# Victor da Cunha
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from slowapi.errors import RateLimitExceeded

# Domain Schemas
from domain.schemas.ProdutoSchema import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse,
    ProdutoPublicResponse
)
from domain.schemas.AuthSchema import FuncionarioAuth
# Infra
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_db
from infra.dependencies import get_current_active_user, require_group
from infra.rate_limit import limiter, get_rate_limit
from services.AuditoriaService import AuditoriaService

router = APIRouter()

# Aplica os filtros opcionais de Produto numa query já existente
def aplicar_filtros_produto(query, id, nome, descricao, valor, valor_min, valor_max):
    if id is not None:
        query = query.filter(ProdutoDB.id == id)
    if nome is not None:
        query = query.filter(ProdutoDB.nome.ilike(f"%{nome}%"))
    if descricao is not None:
        query = query.filter(ProdutoDB.descricao.ilike(f"%{descricao}%"))
    if valor is not None:
        query = query.filter(ProdutoDB.valor_unitario == valor)
    if valor_min is not None:
        query = query.filter(ProdutoDB.valor_unitario >= valor_min)
    if valor_max is not None:
        query = query.filter(ProdutoDB.valor_unitario <= valor_max)
    return query

# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/produto/publico/", response_model=List[ProdutoPublicResponse], tags=["Produto"], status_code=status.HTTP_200_OK, summary="Listar produtos - pública")
@limiter.limit(get_rate_limit("light"))
async def get_produto_publico(
    request: Request,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Quantidade de registros a serem ignorados"),
    limit: int = Query(100, ge=1, le=1000, description="Quantidade máxima de registros retornados"),
    id: Optional[int] = Query(None, description="Filtrar por ID"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    descricao: Optional[str] = Query(None, description="Filtrar por descrição"),
    valor: Optional[float] = Query(None, description="Filtrar por valor exato"),
    valor_min: Optional[float] = Query(None, description="Filtrar por valor mínimo, maior ou igual"),
    valor_max: Optional[float] = Query(None, description="Filtrar por valor máximo, menor ou igual"),
):
    try:
        query = db.query(ProdutoDB)
        query = aplicar_filtros_produto(query, id, nome, descricao, valor, valor_min, valor_max)
        produtos = query.offset(skip).limit(limit).all()
        return produtos
    except RateLimitExceeded:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
            )

@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK, summary="Listar todos os produtos - protegida por autenticação")
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(
    request: Request,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Quantidade de registros a serem ignorados"),
    limit: int = Query(100, ge=1, le=1000, description="Quantidade máxima de registros retornados"),
    id: Optional[int] = Query(None, description="Filtrar por ID"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    descricao: Optional[str] = Query(None, description="Filtrar por descrição"),
    valor: Optional[float] = Query(None, description="Filtrar por valor exato"),
    valor_min: Optional[float] = Query(None, description="Filtrar por valor mínimo, maior ou igual"),
    valor_max: Optional[float] = Query(None, description="Filtrar por valor máximo, menor ou igual"),
):
    try:
        query = db.query(ProdutoDB)
        query = aplicar_filtros_produto(query, id, nome, descricao, valor, valor_min, valor_max)
        produtos = query.offset(skip).limit(limit).all()
        return produtos
    except RateLimitExceeded:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
            )

@router.get("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK, summary="Buscar produto por ID - protegida por autenticação")
@limiter.limit(get_rate_limit("moderate"))
async def get_produto_by_id(request: Request, id: int, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        return produto
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produto: {str(e)}"
            )

@router.post("/produto/", response_model=ProdutoResponse, status_code=status.HTTP_201_CREATED, tags=["Produto"], summary="Criar novo produto - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("restrictive"))
async def post_produto(request: Request, produto_data: ProdutoCreate, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        novo_produto = ProdutoDB(
            id=None,
            nome=produto_data.nome,
            descricao=produto_data.descricao,
            foto=produto_data.foto,
            valor_unitario=produto_data.valor_unitario
        )
        db.add(novo_produto)
        db.commit()
        db.refresh(novo_produto)
        # Depois de tudo executado e antes do return, registra a ação na auditoria
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="PRODUTO",
            recurso_id=novo_produto.id,
            dados_antigos=None,
            dados_novos=novo_produto,
            request=request
        )
        return novo_produto
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar produto: {str(e)}"
        )

@router.put("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK, summary="Atualizar produto - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("restrictive"))
async def put_produto(request: Request, id: int, produto_data: ProdutoUpdate, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado"
            )
        # armazena uma copia do objeto com os dados atuais, para salvar na auditoria
        dados_antigos_obj = produto
        # Atualiza apenas os campos fornecidos
        update_data = produto_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(produto, field, value)
        db.commit()
        db.refresh(produto)
        # Depois de tudo executado e antes do return, registra a ação na auditoria
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=dados_antigos_obj,
            dados_novos=produto,
            request=request
        )
        return produto
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar produto: {str(e)}"
        )

@router.delete("/produto/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Produto"], summary="Remover produto - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("critical"))
async def delete_produto(request: Request, id: int, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto não encontrado"
            )
        db.delete(produto)
        db.commit()
        # Depois de tudo executado e antes do return, registra a ação na auditoria
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=produto,
            dados_novos=None,
            request=request
        )
        return None
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar produto: {str(e)}"
        )
