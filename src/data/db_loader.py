import pandas as pd
import logging
# Ajusta los imports según tu estructura de carpetas
from src.config.db_config import DBConfig
from src.data.clean_data import DataCleaner

logger = logging.getLogger(__name__)

class DataLoader:
    
    @staticmethod
    def load_and_clean_data():
        """
        1. Conecta a SQL.
        2. Descarga tablas crudas.
        3. Aplica limpieza (DataCleaner).
        4. Retorna los DataFrames limpios indivudales.
        """
        engine = DBConfig.get_engine()
        
        try:
            logger.info("Cargando tablas desde SQL Server...")
            clientes = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Clientes", engine)
            destinos = pd.read_sql("SELECT DestinoID, nombre_completo, distancia_km, provinciaID FROM BDIADelivery.dbo.Destinos", engine)
            lineas = pd.read_sql("SELECT * FROM BDIADelivery.dbo.LineasPedido", engine)
            pedidos = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Pedidos", engine)
            productos = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Productos", engine)
            #provincias = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Provincias", engine)
            provincias = pd.read_csv(
                'src/data/provincias_geo.csv',
                dtype={'ProvinciaID': 'int64'}
            )


            # Usamos tu clase DataCleaner original
            logger.info("Ejecutando limpieza de datos...")
            return DataCleaner.clean_full_dataset(clientes, destinos, lineas, pedidos, productos, provincias)

        except Exception as e:
            logger.error(f"Error en carga de datos: {e}")
            raise e