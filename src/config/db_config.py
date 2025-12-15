import logging
from sqlalchemy import create_engine

# Configuración de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DBConfig:
    SERVER = '10.0.40.12'
    PORT = '1433'
    DATABASE = 'master'
    USERNAME = 'sa'
    PASSWORD = 'Stucom.2025'

    @classmethod
    def get_connection_url(db):
        return (
            f"mssql+pyodbc://{db.USERNAME}:{db.PASSWORD}@{db.SERVER}:{db.PORT}/{db.DATABASE}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&Encrypt=no&TrustServerCertificate=yes"
        )

    @classmethod
    def get_engine(db):
        try:
            url = db.get_connection_url()
            engine = create_engine(url)
            logger.info("Conectado a la base de datos correctamente")
            return engine
        except Exception as e:
            logger.error(f"Error al conectar con la base de datos: {e}")
            raise e