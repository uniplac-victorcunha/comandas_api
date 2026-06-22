# Victor da Cunha
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from domain.schemas.FuncionarioSchema import FuncionarioResponse
from domain.schemas.ClienteSchema import ClienteResponse
from domain.schemas.ComandaSchema import ComandaProdutosResponse


class RecebimentoDashboardItem(BaseModel):
    id: int
    comanda: str
    status: int
    cliente: Optional[ClienteResponse] = None
    total: float
    quantidade_produtos: int
    data_hora: datetime


class ComandaDetalheResponse(BaseModel):
    id: int
    comanda: str
    status: int
    cliente: Optional[ClienteResponse] = None
    funcionario: Optional[FuncionarioResponse] = None
    produtos: List[ComandaProdutosResponse]
    total: float
    data_hora: datetime


class RecebimentoCompletoRequest(BaseModel):
    comandas_ids: List[int]
    cliente_id: Optional[int] = None
    funcionario_id: int
    desconto_valor: Optional[float] = None
    acrescimo_valor: Optional[float] = None


class ComandaPaga(BaseModel):
    comanda_id: int
    comanda: str
    subtotal: float


class RecebimentoCompletoResponse(BaseModel):
    sucesso: bool
    mensagem: str
    recebimento_id: int
    comandas_pagas: List[ComandaPaga]
    subtotal_geral: float
    desconto_total: float
    acrescimo_total: float
    valor_final: float
    cliente: Optional[ClienteResponse] = None
    funcionario: FuncionarioResponse
    data_hora: datetime


class RecebimentoCabecalho(BaseModel):
    titulo: str
    sistema: str
    recebimento_id: int
    data_hora: datetime


class ComprovanteItemProduto(BaseModel):
    produto_id: int
    nome: str
    quantidade: int
    valor_unitario: float
    valor_total: float


class ComprovanteComanda(BaseModel):
    comanda_id: int
    comanda: str
    itens: List[ComprovanteItemProduto]
    subtotal: float


class ResumoValores(BaseModel):
    subtotal_geral: float
    desconto_total: float
    acrescimo_total: float
    valor_final: float


class RecebimentoInfo(BaseModel):
    id: int
    data_hora: datetime
    funcionario_id: int
    cliente_id: Optional[int] = None


class RecebimentoRodape(BaseModel):
    mensagem: str


class ComprovanteRecebimento(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cabecalho: RecebimentoCabecalho
    cliente: Optional[ClienteResponse] = None
    funcionario: FuncionarioResponse
    comandas: List[ComprovanteComanda]
    resumo_valores: ResumoValores
    recebimento: RecebimentoInfo
    rodape: RecebimentoRodape
    data_emissao: datetime
