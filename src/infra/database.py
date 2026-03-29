# Victor da Cunha
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from settings import STR_DATABASE
from sqlalchemy.orm import Session

# cria o engine do banco de dados
engine = create_engine(STR_DATABASE, echo=True)
# cria a sessão do banco de dados
Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)
# para trabalhar com tabelas
Base = declarative_base()
# cria, caso não existam, as tabelas de todos os modelos que encontrar na aplicação (importados)
async def cria_tabelas():
    from infra.orm.FuncionarioModel import FuncionarioDB
    from infra.security import get_password_hash
    Base.metadata.create_all(engine)
    # seed: cria admin padrão se não existir nenhum funcionário
    db_session = Session()
    try:
        if not db_session.query(FuncionarioDB).first():
            admin = FuncionarioDB(
                id=None,
                nome="Admin",
                matricula="0000000001",
                cpf="00000000000",
                telefone="00000000000",
                grupo=1,
                senha=get_password_hash("admin123")
            )
            db_session.add(admin)
            db_session.commit()
            print("Seed: funcionário admin criado (CPF: 00000000000 / senha: admin123)")
    finally:
        db_session.close()
# dependência para injetar a sessão do banco de dados nas rotas
def get_db():
    db_session = Session()
    try:
        yield db_session
    finally:
        db_session.close()