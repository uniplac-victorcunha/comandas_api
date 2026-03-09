# Victor da Cunha
from dotenv import load_dotenv, find_dotenv
import os

dotenv_file = find_dotenv()

load_dotenv(dotenv_file)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = os.getenv("PORT", "8000")
RELOAD = os.getenv("RELOAD", True)

DB_SGDB = os.getenv("DB_SGDB")
DB_NAME = os.getenv("DB_NAME")

# Ajusta STR_DATABASE conforme gerenciador escolhido
if DB_SGDB == 'sqlite': # SQLite
    STR_DATABASE = f"sqlite:///{DB_NAME}.db"
elif DB_SGDB == 'mysql': # MySQL
    import pymysql
    STR_DATABASE = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
elif DB_SGDB == 'mssql': # SQL Server
    import pymssql
    STR_DATABASE = f"mssql+pymssql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8"
else: # SQLite
    STR_DATABASE = f"sqlite:///comandas_db.db"