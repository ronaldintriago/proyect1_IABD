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

    @staticmethod
    def get_master_view():
        """
        Genera la 'Tabla Maestra' unificada lista para el Dashboard.
        Encapsula toda la lógica de los MERGES aquí.
        """
        # 1. Obtenemos datos limpios
        clientes, destinos, lineas, pedidos, productos, provincias = DataLoader.load_and_clean_data()
        
        logger.info("Unificando tablas (Merging)...")
        
        # Merge 1: Lineas + Pedidos
        df = pd.merge(lineas, pedidos, on="PedidoID", how="left")
        
        # Merge 2: + Productos
        df = pd.merge(df, productos, on="ProductoID", how="left", suffixes=('_linea', '_prod'))
        
        # Merge 3: + Clientes
        clientes = clientes.rename(columns={'nombre': 'Nombre_Cliente'})
        df = pd.merge(df, clientes, on="ClienteID", how="left")
        
        # Merge 4: + Destinos
        df = pd.merge(df, destinos, left_on="DestinoEntregaID", right_on="DestinoID", how="left")
        
        df['provinciaID'] = (
            df['provinciaID']
            .astype('Int64')  # permite NaN
        )

        # Merge 5: + Provincias
        provincias = provincias.rename(columns={'nombre': 'Nombre_Provincia'})
        df = pd.merge(df, provincias, left_on="provinciaID", right_on="ProvinciaID", how="left")
        
        # Cálculos finales
        df['Total_Linea'] = df['Cantidad'] * df['PrecioVenta']
        
        # Renombrar para frontend
        df = df.rename(columns={
            'Nombre': 'Producto', 
            'nombre_completo': 'Destino', 
            'distancia_km': 'Distancia_Km'
        })
        
        # Selección de columnas finales
        cols = ['PedidoID', 'FechaPedido', 'Nombre_Cliente', 'Producto', 
                'Cantidad', 'PrecioVenta', 'Total_Linea', 'Destino', 'Latitud', 'Longitud'
                'Nombre_Provincia', 'Distancia_Km', 'email']
        
        # Filtrar solo columnas existentes (por seguridad)
        cols = [c for c in cols if c in df.columns]
        
        return df[cols], (clientes, destinos, lineas, pedidos, productos, provincias)