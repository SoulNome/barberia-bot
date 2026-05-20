import os
from dotenv import load_dotenv

load_dotenv()

class Config:

    SECRET_KEY = os.getenv("SECRET_KEY", "dev_key")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///barberia.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pool de conexiones: pequeño para ahorrar RAM, pre_ping para auto-reconexión
    # cuando Postgres se reinicia (Railway incidents, deploys, etc.)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size":    2,       # conexiones persistentes (default 5)
        "max_overflow": 3,       # extra bajo carga pico (default 10)
        "pool_timeout": 20,      # seg esperando conexión libre (default 30)
        "pool_recycle": 1800,    # recicla conexiones cada 30 min
        "pool_pre_ping": True,   # valida conexión antes de usarla → auto-reconexión
    }

    # Evolution API
    EVOLUTION_API_URL      = os.getenv("EVOLUTION_API_URL", "")
    EVOLUTION_API_KEY      = os.getenv("EVOLUTION_API_KEY", "")
    EVOLUTION_INSTANCE     = os.getenv("EVOLUTION_INSTANCE", "")
