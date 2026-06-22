# Victor da Cunha
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime
from slowapi.errors import RateLimitExceeded

from domain.schemas.RecebimentoSchema import (
    RecebimentoDashboardItem, ComandaDetalheResponse,
    RecebimentoCompletoRequest, RecebimentoCompletoResponse, ComandaPaga,
    ComprovanteRecebimento, RecebimentoCabecalho, ComprovanteComanda,
    ComprovanteItemProduto, ResumoValores, RecebimentoInfo, RecebimentoRodape
)
from domain.schemas.AuthSchema import FuncionarioAuth
from infra.orm.ComandaModel import ComandaDB, ComandaProdutoDB
from infra.orm.RecebimentoModel import RecebimentoDB, RecebimentoComandaDB
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.orm.ClienteModel import ClienteDB
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_async_db, Session as SyncSession
from infra.dependencies import require_group
from infra.rate_limit import limiter, get_rate_limit
from services.AuditoriaService import AuditoriaService

router = APIRouter()


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


async def _buscar_comanda_aberta(db: AsyncSession, comanda_id: int) -> ComandaDB:
    result = await db.execute(select(ComandaDB).where(ComandaDB.id == comanda_id))
    comanda = result.scalar_one_or_none()
    if not comanda:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Comanda {comanda_id} não encontrada")
    return comanda


async def _produtos_da_comanda(db: AsyncSession, comanda_id: int) -> List[ComandaProdutoDB]:
    result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.comanda_id == comanda_id))
    return result.scalars().all()


@router.get("/recebimento/dashboard", response_model=List[RecebimentoDashboardItem], tags=["Recebimento"],
            status_code=status.HTTP_200_OK, summary="Dashboard completo com comandas abertas e fotos")
@limiter.limit(get_rate_limit("moderate"))
async def get_recebimento_dashboard(request: Request,
                                    db: AsyncSession = Depends(get_async_db),
                                    current_user: FuncionarioAuth = Depends(require_group([1, 3]))):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.status == 0))
        comandas = result.scalars().all()
        itens = []
        for comanda in comandas:
            produtos = await _produtos_da_comanda(db, comanda.id)
            total = sum(float(p.valor_unitario) * p.quantidade for p in produtos)
            quantidade_produtos = sum(p.quantidade for p in produtos)
            cliente = None
            if comanda.cliente_id:
                cli_result = await db.execute(select(ClienteDB).where(ClienteDB.id == comanda.cliente_id))
                cliente = cli_result.scalar_one_or_none()
            itens.append({
                "id": comanda.id,
                "comanda": comanda.comanda,
                "status": comanda.status,
                "cliente": cliente,
                "total": total,
                "quantidade_produtos": quantidade_produtos,
                "data_hora": comanda.data_hora,
            })
        return itens
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao buscar dashboard de recebimento: {str(e)}")


@router.get("/recebimento/comandas/detalhe/{comandas_ids}", response_model=List[ComandaDetalheResponse],
            tags=["Recebimento"], status_code=status.HTTP_200_OK, summary="Detalhar comandas para recebimento")
@limiter.limit(get_rate_limit("moderate"))
async def get_recebimento_comandas_detalhe(request: Request, comandas_ids: str,
                                           db: AsyncSession = Depends(get_async_db),
                                           current_user: FuncionarioAuth = Depends(require_group([1, 3]))):
    try:
        try:
            ids = [int(i) for i in comandas_ids.split(",") if i.strip() != ""]
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="comandas_ids deve ser uma lista de números separados por vírgula")
        if not ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum ID de comanda informado")
        detalhes = []
        for comanda_id in ids:
            comanda = await _buscar_comanda_aberta(db, comanda_id)
            produtos = await _produtos_da_comanda(db, comanda.id)
            produtos_resp = []
            for item in produtos:
                prod_result = await db.execute(select(ProdutoDB).where(ProdutoDB.id == item.produto_id))
                produto = prod_result.scalar_one_or_none()
                func_result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == item.funcionario_id))
                funcionario_item = func_result.scalar_one_or_none()
                produtos_resp.append({
                    "id": item.id,
                    "comanda_id": item.comanda_id,
                    "funcionario_id": item.funcionario_id,
                    "funcionario": funcionario_item,
                    "produto_id": item.produto_id,
                    "produto": produto,
                    "quantidade": item.quantidade,
                    "valor_unitario": item.valor_unitario,
                })
            total = sum(float(p.valor_unitario) * p.quantidade for p in produtos)
            cliente = None
            if comanda.cliente_id:
                cli_result = await db.execute(select(ClienteDB).where(ClienteDB.id == comanda.cliente_id))
                cliente = cli_result.scalar_one_or_none()
            func_result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == comanda.funcionario_id))
            funcionario = func_result.scalar_one_or_none()
            detalhes.append({
                "id": comanda.id,
                "comanda": comanda.comanda,
                "status": comanda.status,
                "cliente": cliente,
                "funcionario": funcionario,
                "produtos": produtos_resp,
                "total": total,
                "data_hora": comanda.data_hora,
            })
        return detalhes
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao detalhar comandas: {str(e)}")


@router.post("/recebimento/completo", response_model=RecebimentoCompletoResponse, tags=["Recebimento"],
             status_code=status.HTTP_201_CREATED, summary="Recebimento completo com desconto/acréscimo")
@limiter.limit(get_rate_limit("restrictive"))
async def post_recebimento_completo(request: Request, recebimento_data: RecebimentoCompletoRequest,
                                    db: AsyncSession = Depends(get_async_db),
                                    current_user: FuncionarioAuth = Depends(require_group([1, 3]))):
    try:
        if not recebimento_data.comandas_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Nenhuma comanda informada para recebimento")

        func_result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == recebimento_data.funcionario_id))
        funcionario = func_result.scalar_one_or_none()
        if not funcionario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funcionário não encontrado")

        cliente = None
        if recebimento_data.cliente_id:
            cli_result = await db.execute(select(ClienteDB).where(ClienteDB.id == recebimento_data.cliente_id))
            cliente = cli_result.scalar_one_or_none()
            if not cliente:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")

        comandas_subtotais = []
        for comanda_id in recebimento_data.comandas_ids:
            comanda = await _buscar_comanda_aberta(db, comanda_id)
            if comanda.status != 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Comanda {comanda.comanda} não está aberta")
            produtos = await _produtos_da_comanda(db, comanda.id)
            subtotal = sum(float(p.valor_unitario) * p.quantidade for p in produtos)
            comandas_subtotais.append((comanda, subtotal))

        subtotal_geral = sum(subtotal for _, subtotal in comandas_subtotais)
        desconto_total = recebimento_data.desconto_valor or 0
        acrescimo_total = recebimento_data.acrescimo_valor or 0
        valor_final = subtotal_geral - desconto_total + acrescimo_total

        novo_recebimento = RecebimentoDB(
            cliente_id=recebimento_data.cliente_id,
            funcionario_id=recebimento_data.funcionario_id,
            subtotal_geral=subtotal_geral,
            desconto_total=desconto_total,
            acrescimo_total=acrescimo_total,
            valor_final=valor_final,
            data_hora=datetime.now()
        )
        db.add(novo_recebimento)
        await db.flush()

        comandas_pagas = []
        for comanda, subtotal in comandas_subtotais:
            comanda.status = 1
            if recebimento_data.cliente_id:
                comanda.cliente_id = recebimento_data.cliente_id
            db.add(RecebimentoComandaDB(
                recebimento_id=novo_recebimento.id,
                comanda_id=comanda.id,
                subtotal=subtotal
            ))
            comandas_pagas.append(ComandaPaga(comanda_id=comanda.id, comanda=comanda.comanda, subtotal=subtotal))

        await db.commit()
        await db.refresh(novo_recebimento)
        _registrar_auditoria(current_user.id, "CREATE", "RECEBIMENTO", novo_recebimento.id, None, novo_recebimento, request)

        return RecebimentoCompletoResponse(
            sucesso=True,
            mensagem="Recebimento realizado com sucesso",
            recebimento_id=novo_recebimento.id,
            comandas_pagas=comandas_pagas,
            subtotal_geral=subtotal_geral,
            desconto_total=desconto_total,
            acrescimo_total=acrescimo_total,
            valor_final=valor_final,
            cliente=cliente,
            funcionario=funcionario,
            data_hora=novo_recebimento.data_hora
        )
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao processar recebimento: {str(e)}")


@router.get("/recebimento/comprovante/{recebimento_id}", response_model=ComprovanteRecebimento, tags=["Recebimento"],
            status_code=status.HTTP_200_OK, summary="Gerar comprovante de recebimento")
@limiter.limit(get_rate_limit("moderate"))
async def get_recebimento_comprovante(request: Request, recebimento_id: int,
                                      db: AsyncSession = Depends(get_async_db),
                                      current_user: FuncionarioAuth = Depends(require_group([1, 3]))):
    try:
        result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == recebimento_id))
        recebimento = result.scalar_one_or_none()
        if not recebimento:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recebimento não encontrado")

        func_result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == recebimento.funcionario_id))
        funcionario = func_result.scalar_one_or_none()

        cliente = None
        if recebimento.cliente_id:
            cli_result = await db.execute(select(ClienteDB).where(ClienteDB.id == recebimento.cliente_id))
            cliente = cli_result.scalar_one_or_none()

        vinc_result = await db.execute(
            select(RecebimentoComandaDB).where(RecebimentoComandaDB.recebimento_id == recebimento_id)
        )
        vinculos = vinc_result.scalars().all()

        comandas_comprovante = []
        for vinculo in vinculos:
            comanda_result = await db.execute(select(ComandaDB).where(ComandaDB.id == vinculo.comanda_id))
            comanda = comanda_result.scalar_one_or_none()
            produtos = await _produtos_da_comanda(db, vinculo.comanda_id)
            itens = []
            for item in produtos:
                prod_result = await db.execute(select(ProdutoDB).where(ProdutoDB.id == item.produto_id))
                produto = prod_result.scalar_one_or_none()
                itens.append(ComprovanteItemProduto(
                    produto_id=item.produto_id,
                    nome=produto.nome if produto else "Produto não encontrado",
                    quantidade=item.quantidade,
                    valor_unitario=item.valor_unitario,
                    valor_total=float(item.valor_unitario) * item.quantidade
                ))
            comandas_comprovante.append(ComprovanteComanda(
                comanda_id=vinculo.comanda_id,
                comanda=comanda.comanda if comanda else str(vinculo.comanda_id),
                itens=itens,
                subtotal=vinculo.subtotal
            ))

        return ComprovanteRecebimento(
            cabecalho=RecebimentoCabecalho(
                titulo="Comprovante de Recebimento",
                sistema="Comandas do Zé",
                recebimento_id=recebimento.id,
                data_hora=recebimento.data_hora
            ),
            cliente=cliente,
            funcionario=funcionario,
            comandas=comandas_comprovante,
            resumo_valores=ResumoValores(
                subtotal_geral=recebimento.subtotal_geral,
                desconto_total=recebimento.desconto_total,
                acrescimo_total=recebimento.acrescimo_total,
                valor_final=recebimento.valor_final
            ),
            recebimento=RecebimentoInfo(
                id=recebimento.id,
                data_hora=recebimento.data_hora,
                funcionario_id=recebimento.funcionario_id,
                cliente_id=recebimento.cliente_id
            ),
            rodape=RecebimentoRodape(mensagem="Obrigado pela preferência! Volte sempre."),
            data_emissao=datetime.now()
        )
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao gerar comprovante: {str(e)}")
