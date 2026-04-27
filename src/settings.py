# Victor da Cunha
from dotenv import load_dotenv
import os

dotenv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

load_dotenv(dotenv_file)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = os.getenv("PORT", "8000")
RELOAD = os.getenv("RELOAD", True)

DB_SGDB = os.getenv("DB_SGBD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ajusta STR_DATABASE conforme gerenciador escolhido
if DB_SGDB == 'sqlite': # SQLite
    STR_DATABASE = f"sqlite:///{BASE_DIR}/{DB_NAME}.db?foreign_keys=1"
elif DB_SGDB == 'mysql': # MySQL
    import pymysql
    STR_DATABASE = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
elif DB_SGDB == 'mssql': # SQL Server
    import pymssql
    STR_DATABASE = f"mssql+pymssql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8"
else: # SQLite
    STR_DATABASE = f"sqlite:///{BASE_DIR}/apiDatabase.db?foreign_keys=1"

SECRET_KEY = os.getenv("SECRET_KEY", "chave-padrao-insegura")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Async DB string
if STR_DATABASE.startswith("sqlite:///"):
    ASYNC_STR_DATABASE = STR_DATABASE.replace("sqlite:///", "sqlite+aiosqlite:///")
elif STR_DATABASE.startswith("sqlite://"):
    ASYNC_STR_DATABASE = STR_DATABASE.replace("sqlite://", "sqlite+aiosqlite:///")
elif DB_SGDB == 'mysql':
    ASYNC_STR_DATABASE = STR_DATABASE.replace("mysql+pymysql://", "mysql+aiomysql://")
elif DB_SGDB == 'mssql':
    ASYNC_STR_DATABASE = STR_DATABASE
elif DB_SGDB == 'postgresql':
    ASYNC_STR_DATABASE = STR_DATABASE.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_STR_DATABASE = STR_DATABASE

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else "*"
