# Victor da Cunha
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime, date
from slowapi.errors import RateLimitExceeded

from domain.schemas.ComandaSchema import (
    ComandaCreate, ComandaUpdate, ComandaResponse,
    ComandaProdutosCreate, ComandaProdutosUpdate, ComandaProdutosResponse
)
from domain.schemas.AuthSchema import FuncionarioAuth
from infra.orm.ComandaModel import ComandaDB, ComandaProdutoDB
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.orm.ClienteModel import ClienteDB
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_async_db, Session as SyncSession
from infra.dependencies import get_current_active_user, require_group
from infra.rate_limit import limiter, get_rate_limit
from services.AuditoriaService import AuditoriaService

router = APIRouter()


async def _build_comanda_response(db: AsyncSession, comanda: ComandaDB) -> dict:
    func_result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == comanda.funcionario_id))
    funcionario = func_result.scalar_one_or_none()

    cliente = None
    if comanda.cliente_id:
        cli_result = await db.execute(select(ClienteDB).where(ClienteDB.id == comanda.cliente_id))
        cliente = cli_result.scalar_one_or_none()

    return {
        "id": comanda.id,
        "comanda": comanda.comanda,
        "data_hora": comanda.data_hora,
        "status": comanda.status,
        "funcionario_id": comanda.funcionario_id,
        "funcionario": funcionario,
        "cliente_id": comanda.cliente_id,
        "cliente": cliente,
    }


async def _build_produto_response(db: AsyncSession, item: ComandaProdutoDB) -> dict:
    func_result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == item.funcionario_id))
    funcionario = func_result.scalar_one_or_none()

    prod_result = await db.execute(select(ProdutoDB).where(ProdutoDB.id == item.produto_id))
    produto = prod_result.scalar_one_or_none()

    return {
        "id": item.id,
        "comanda_id": item.comanda_id,
        "funcionario_id": item.funcionario_id,
        "funcionario": funcionario,
        "produto_id": item.produto_id,
        "produto": produto,
        "quantidade": item.quantidade,
        "valor_unitario": item.valor_unitario,
    }


def _registrar_auditoria(funcionario_id: int, acao: str, recurso: str, recurso_id: int,
                          dados_antigos, dados_novos, request: Request):
    sync_db = SyncSession()
    try:
        AuditoriaService.registrar_acao(
            db=sync_db,
            funcionario_id=funcionario_id,
            acao=acao,
            recurso=recurso,
            recurso_id=recurso_id,
            dados_antigos=dados_antigos,
            dados_novos=dados_novos,
            request=request
        )
    finally:
        sync_db.close()


@router.get("/comanda/{id}", response_model=ComandaResponse, tags=["Comanda"],
            status_code=status.HTTP_200_OK, summary="Buscar comanda por ID - protegida por autenticação")
@limiter.limit(get_rate_limit("moderate"))
async def get_comanda_by_id(request: Request, id: int,
                             db: AsyncSession = Depends(get_async_db),
                             current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        return await _build_comanda_response(db, comanda)
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao buscar comanda: {str(e)}")


@router.get("/comanda/", response_model=List[ComandaResponse], tags=["Comanda"],
            status_code=status.HTTP_200_OK, summary="Listar comandas - protegida por autenticação")
@limiter.limit(get_rate_limit("moderate"))
async def get_comandas(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    id: Optional[int] = Query(None),
    comanda: Optional[str] = Query(None),
    status_filtro: Optional[int] = Query(None, alias="status"),
    funcionario_id: Optional[int] = Query(None),
    cliente_id: Optional[int] = Query(None),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    try:
        query = select(ComandaDB)
        filtros = []
        if id is not None:
            filtros.append(ComandaDB.id == id)
        if comanda is not None:
            filtros.append(ComandaDB.comanda.ilike(f"%{comanda}%"))
        if status_filtro is not None:
            filtros.append(ComandaDB.status == status_filtro)
        if funcionario_id is not None:
            filtros.append(ComandaDB.funcionario_id == funcionario_id)
        if cliente_id is not None:
            filtros.append(ComandaDB.cliente_id == cliente_id)
        if data_inicio is not None:
            filtros.append(ComandaDB.data_hora >= datetime.combine(data_inicio, datetime.min.time()))
        if data_fim is not None:
            filtros.append(ComandaDB.data_hora <= datetime.combine(data_fim, datetime.max.time()))
        if filtros:
            query = query.where(and_(*filtros))
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        comandas = result.scalars().all()
        return [await _build_comanda_response(db, c) for c in comandas]
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao listar comandas: {str(e)}")


@router.post("/comanda/", response_model=ComandaResponse, tags=["Comanda"],
             status_code=status.HTTP_201_CREATED, summary="Criar comanda - protegida por autenticação")
@limiter.limit(get_rate_limit("restrictive"))
async def post_comanda(request: Request, comanda_data: ComandaCreate,
                       db: AsyncSession = Depends(get_async_db),
                       current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        if comanda_data.status != 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Nova comanda deve ter status 0 (aberta)")
        # verifica se já existe comanda aberta com o mesmo nome
        result = await db.execute(
            select(ComandaDB).where(and_(ComandaDB.comanda == comanda_data.comanda, ComandaDB.status == 0))
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Já existe uma comanda aberta com esse nome")
        nova_comanda = ComandaDB(
            comanda=comanda_data.comanda,
            data_hora=datetime.now(),
            status=comanda_data.status,
            cliente_id=comanda_data.cliente_id,
            funcionario_id=comanda_data.funcionario_id
        )
        db.add(nova_comanda)
        await db.commit()
        await db.refresh(nova_comanda)
        _registrar_auditoria(current_user.id, "CREATE", "COMANDA", nova_comanda.id, None, nova_comanda, request)
        return await _build_comanda_response(db, nova_comanda)
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao criar comanda: {str(e)}")


@router.put("/comanda/{id}", response_model=ComandaResponse, tags=["Comanda"],
            status_code=status.HTTP_200_OK, summary="Atualizar comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("restrictive"))
async def put_comanda(request: Request, id: int, comanda_data: ComandaUpdate,
                      db: AsyncSession = Depends(get_async_db),
                      current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        dados_antigos = comanda
        update_data = comanda_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(comanda, field, value)
        await db.commit()
        await db.refresh(comanda)
        _registrar_auditoria(current_user.id, "UPDATE", "COMANDA", comanda.id, dados_antigos, comanda, request)
        return await _build_comanda_response(db, comanda)
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao atualizar comanda: {str(e)}")


@router.delete("/comanda/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Comanda"],
               summary="Remover comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("critical"))
async def delete_comanda(request: Request, id: int,
                         db: AsyncSession = Depends(get_async_db),
                         current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        # verifica se há produtos vinculados
        prod_result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.comanda_id == id))
        if prod_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Comanda possui produtos vinculados, remova-os antes de excluir")
        dados_antigos = comanda
        await db.delete(comanda)
        await db.commit()
        _registrar_auditoria(current_user.id, "DELETE", "COMANDA", id, dados_antigos, None, request)
        return None
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao deletar comanda: {str(e)}")


@router.put("/comanda/{id}/cancelar", response_model=ComandaResponse, tags=["Comanda"],
            status_code=status.HTTP_200_OK, summary="Cancelar comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("restrictive"))
async def cancelar_comanda(request: Request, id: int,
                           db: AsyncSession = Depends(get_async_db),
                           current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        if comanda.status == 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comanda já está cancelada")
        dados_antigos = comanda
        comanda.status = 2
        await db.commit()
        await db.refresh(comanda)
        _registrar_auditoria(current_user.id, "CANCEL", "COMANDA", comanda.id, dados_antigos, comanda, request)
        return await _build_comanda_response(db, comanda)
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao cancelar comanda: {str(e)}")


@router.post("/comanda/{comanda_id}/produto", response_model=ComandaProdutosResponse, tags=["Comanda"],
             status_code=status.HTTP_201_CREATED, summary="Adicionar produto à comanda - protegida por autenticação")
@limiter.limit(get_rate_limit("restrictive"))
async def post_comanda_produto(request: Request, comanda_id: int, produto_data: ComandaProdutosCreate,
                               db: AsyncSession = Depends(get_async_db),
                               current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == comanda_id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        if comanda.status != 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Somente comandas abertas (status 0) aceitam produtos")
        novo_item = ComandaProdutoDB(
            comanda_id=comanda_id,
            produto_id=produto_data.produto_id,
            funcionario_id=produto_data.funcionario_id,
            quantidade=produto_data.quantidade,
            valor_unitario=produto_data.valor_unitario
        )
        db.add(novo_item)
        await db.commit()
        await db.refresh(novo_item)
        _registrar_auditoria(current_user.id, "CREATE", "COMANDA_PRODUTO", novo_item.id, None, novo_item, request)
        return await _build_produto_response(db, novo_item)
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao adicionar produto à comanda: {str(e)}")


@router.get("/comanda/{id}/produtos", response_model=List[ComandaProdutosResponse], tags=["Comanda"],
            status_code=status.HTTP_200_OK, summary="Listar produtos da comanda - protegida por autenticação")
@limiter.limit(get_rate_limit("moderate"))
async def get_comanda_produtos(request: Request, id: int,
                               db: AsyncSession = Depends(get_async_db),
                               current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        prod_result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.comanda_id == id))
        itens = prod_result.scalars().all()
        return [await _build_produto_response(db, item) for item in itens]
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao listar produtos da comanda: {str(e)}")


@router.put("/comanda/produto/{id}", response_model=ComandaProdutosResponse, tags=["Comanda"],
            status_code=status.HTTP_200_OK, summary="Atualizar produto da comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("restrictive"))
async def put_comanda_produto(request: Request, id: int, produto_data: ComandaProdutosUpdate,
                              db: AsyncSession = Depends(get_async_db),
                              current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.id == id))
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
        dados_antigos = item
        update_data = produto_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)
        await db.commit()
        await db.refresh(item)
        _registrar_auditoria(current_user.id, "UPDATE", "COMANDA_PRODUTO", item.id, dados_antigos, item, request)
        return await _build_produto_response(db, item)
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao atualizar produto da comanda: {str(e)}")


@router.delete("/comanda/produto/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Comanda"],
               summary="Remover produto da comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("critical"))
async def delete_comanda_produto(request: Request, id: int,
                                 db: AsyncSession = Depends(get_async_db),
                                 current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.id == id))
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
        dados_antigos = item
        await db.delete(item)
        await db.commit()
        _registrar_auditoria(current_user.id, "DELETE", "COMANDA_PRODUTO", id, dados_antigos, None, request)
        return None
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao remover produto da comanda: {str(e)}")
