import pandas as pd
import logging
import os
# Ajusta los imports según tu estructura de carpetas
from src.config.db_config import DBConfig
from src.etl.clean_data import DataCleaner

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
                'data/raw/provincias_geo.csv',
                dtype={'ProvinciaID': 'int64'}
            )


            # Usamos tu clase DataCleaner original
            logger.info("Ejecutando limpieza de datos...")
            return DataCleaner.clean_full_dataset(clientes, destinos, lineas, pedidos, productos, provincias)

        except Exception as e:
            logger.error(f"Error en carga de datos: {e}")
            raise e
        
    @staticmethod
    def get_data_from_csv_files(csv_folder_path="data/raw"):
        """
        Carga los datos desde archivos CSV locales simulando la extracción de SQL.
        Busca archivos que comiencen con el nombre de la tabla (para ignorar fechas en el nombre).
        """
        logger.info(f"📂 Cargando datos desde carpeta CSV: {csv_folder_path}")

        # Diccionario para mapear nombre de tabla -> DataFrame
        tablas = {
            "Clientes": None,
            "Destinos": None,
            "LineasPedido": None,
            "Pedidos": None,
            "Productos": None,
            "Provincias": None
        }

        try:
            # Listar archivos en la carpeta
            available_files = os.listdir(csv_folder_path)

            for tabla_name in tablas.keys():
                # Buscar el archivo que empiece por el nombre de la tabla (ej: "Clientes_2025...")
                file_name = next((f for f in available_files if f.startswith(tabla_name) and f.endswith('.csv')), None)
                
                if not file_name:
                    raise FileNotFoundError(f"No se encontró CSV para la tabla: {tabla_name}")

                full_path = os.path.join(csv_folder_path, file_name)
                
                # Leemos el CSV. Probamos con separador ';' (común en exports) y luego ','
                try:
                    df = pd.read_csv(full_path, sep=',')
                    # Si al leer con coma solo hay 1 columna, probablemente es punto y coma
                    if df.shape[1] < 2:
                        df = pd.read_csv(full_path, sep=';')
                except:
                    # Fallback directo a punto y coma
                    df = pd.read_csv(full_path, sep=';')

                tablas[tabla_name] = df
                logger.info(f"    Cargado: {file_name} ({len(df)} filas)")

            # Extraer DataFrames del diccionario
            clientes = tablas["Clientes"]
            destinos = tablas["Destinos"]
            lineas = tablas["LineasPedido"]
            pedidos = tablas["Pedidos"]
            productos = tablas["Productos"]
            provincias = tablas["Provincias"]

            logger.info(" Carga CSV completada. Ejecutando limpieza...")

            # Devolvemos exactamente lo mismo que el método SQL: la tupla de DFs limpios
            return DataCleaner.clean_full_dataset(clientes, destinos, lineas, pedidos, productos, provincias)

        except Exception as e:
            logger.error(f"❌ Error crítico cargando CSVs: {e}")
            raise e