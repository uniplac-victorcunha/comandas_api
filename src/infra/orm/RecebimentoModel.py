# Victor da Cunha
from sqlalchemy import Column, Integer, DECIMAL, DateTime, ForeignKey
from infra.database import Base


class RecebimentoDB(Base):
    __tablename__ = "tb_recebimento"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    cliente_id = Column(Integer, ForeignKey("tb_cliente.id", ondelete="RESTRICT"), nullable=True, default=None)
    funcionario_id = Column(Integer, ForeignKey("tb_funcionario.id", ondelete="RESTRICT"), nullable=False)
    subtotal_geral = Column(DECIMAL(11, 2), nullable=False)
    desconto_total = Column(DECIMAL(11, 2), nullable=False, default=0)
    acrescimo_total = Column(DECIMAL(11, 2), nullable=False, default=0)
    valor_final = Column(DECIMAL(11, 2), nullable=False)
    data_hora = Column(DateTime, nullable=False)


class RecebimentoComandaDB(Base):
    __tablename__ = "tb_recebimento_comanda"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    recebimento_id = Column(Integer, ForeignKey("tb_recebimento.id", ondelete="RESTRICT"), nullable=False)
    comanda_id = Column(Integer, ForeignKey("tb_comanda.id", ondelete="RESTRICT"), nullable=False)
    subtotal = Column(DECIMAL(11, 2), nullable=False)
