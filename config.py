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

    # Evolution API
    EVOLUTION_API_URL      = os.getenv("EVOLUTION_API_URL", "")
    EVOLUTION_API_KEY      = os.getenv("EVOLUTION_API_KEY", "")
    EVOLUTION_INSTANCE     = os.getenv("EVOLUTION_INSTANCE", "")