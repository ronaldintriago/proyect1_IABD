import pandas as pd
import os
from src.config.db_config import DBConfig 

class DataLoader:
    
    REQUIRED_TABLES = ['Pedidos', 'LineasPedido', 'Productos', 'Clientes', 'Destinos']

    @staticmethod
    def load_from_csv(folder_path="data/raw"):
        """Carga los CSVs locales."""
        print(f"📂 Cargando CSVs desde {folder_path}...")
        dfs = {}
        try:
            files = {
                'Pedidos': 'Pedidos.csv',
                'LineasPedido': 'LineasPedido.csv',
                'Productos': 'Productos.csv',
                'Clientes': 'Clientes.csv',
                'Destinos': 'Destinos.csv',
                'Provincias_geo': 'Provincias_geo.csv'
            }
            
            for key, filename in files.items():
                path = os.path.join(folder_path, filename)
                if os.path.exists(path):
                    # Forzamos sep=',' para evitar problemas si el sistema está en español (;)
                    dfs[key] = pd.read_csv(path, sep=',')
                else:
                    if key != 'Provincias_geo':
                        raise FileNotFoundError(f"Falta el archivo: {filename}")
            
            return dfs
        except Exception as e:
            print(f"❌ Error cargando CSVs: {e}")
            return None

    @staticmethod
    def load_from_sql():
        """Conecta a BBDD y descarga las tablas."""
        print("🔌 Conectando al Servidor SQL...")
        dfs = {}
        try:
            engine = DBConfig.get_engine()
            
            for table in DataLoader.REQUIRED_TABLES:
                print(f"   ⬇️ Descargando tabla: {table}...")
                
                if table == 'Destinos':
                    # --- CORRECCIÓN FINAL BASADA EN TUS DATOS ---
                    # Pedimos solo las columnas que sabemos que existen (según tu CSV)
                    # Saltamos 'coordenadas_gps' que es geography y da error.
                    query = """
                        SELECT DestinoID, nombre_completo, distancia_km, provinciaID 
                        FROM Destinos
                    """
                    dfs[table] = pd.read_sql(query, engine)
                else:
                    dfs[table] = pd.read_sql_table(table, engine)

            # Carga de respaldo para coordenadas (Provincias_geo)
            path_geo = "data/raw/Provincias_geo.csv"
            if os.path.exists(path_geo):
                print("   🌍 Cargando refuerzo de coordenadas (Provincias_geo.csv)...")
                dfs['Provincias_geo'] = pd.read_csv(path_geo, sep=',')
            
            print("✅ Carga SQL completada con éxito.")
            return dfs

        except Exception as e:
            print(f"❌ Error crítico en carga SQL: {e}")
            return None