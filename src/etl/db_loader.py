import pandas as pd
import os
from src.config.db_config import DBConfig 

class DataLoader:
    
    REQUIRED_TABLES = ['Pedidos', 'LineasPedido', 'Productos', 'Clientes', 'Destinos']

    @staticmethod
    def load_manual_buffers(uploaded_files_dict):
        """
        Carga CSVs desde memoria.
        """
        print("📂 Leyendo archivos subidos por el usuario...")
        dfs = {}
        try:
            # 1. Leer lo que subió el usuario (Incluido Provincias.csv si está)
            for key, file_obj in uploaded_files_dict.items():
                if file_obj is not None:
                    file_obj.seek(0)
                    dfs[key] = pd.read_csv(file_obj, sep=',')
                    print(f"   ✅ Leído usuario: {key} ({len(dfs[key])} filas)")
            
            # 2. CARGA HÍBRIDA DE COORDENADAS
            # Siempre cargamos nuestro 'Provincias_geo.csv' interno como caché base.
            # feature.py se encargará de usarlo y, si falta algo, usar 'Provincias' del usuario.
            path_geo_interno = "data/raw/Provincias_geo.csv"
            if os.path.exists(path_geo_interno):
                print("   🌍 Cargando caché de coordenadas interna (Provincias_geo.csv)...")
                dfs['Provincias_geo'] = pd.read_csv(path_geo_interno, sep=',')
            
            # Validación
            if len(dfs) < len(DataLoader.REQUIRED_TABLES):
                faltan = set(DataLoader.REQUIRED_TABLES) - set(dfs.keys())
                print(f"⚠️ Faltan archivos obligatorios: {faltan}")
                return None
                
            return dfs
        except Exception as e:
            print(f"❌ Error leyendo buffers CSV: {e}")
            return None

    @staticmethod
    def load_from_csv(folder_path="data/raw"):
        # (Este método se mantiene igual que la última versión funcional)
        print(f"📂 Cargando CSVs desde {folder_path}...")
        dfs = {}
        try:
            files = {
                'Pedidos': 'Pedidos.csv', 'LineasPedido': 'LineasPedido.csv',
                'Productos': 'Productos.csv', 'Clientes': 'Clientes.csv',
                'Destinos': 'Destinos.csv', 'Provincias_geo': 'Provincias_geo.csv',
                'Provincias': 'Provincias.csv' 
            }
            for key, filename in files.items():
                path = os.path.join(folder_path, filename)
                if os.path.exists(path):
                    dfs[key] = pd.read_csv(path, sep=',')
                elif key not in ['Provincias_geo', 'Provincias']: # Opcionales
                    raise FileNotFoundError(f"Falta: {filename}")
            return dfs
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    @staticmethod
    def load_from_sql():
        # (Este método se mantiene igual, con el fix de Destinos)
        print("🔌 Conectando SQL...")
        dfs = {}
        try:
            engine = DBConfig.get_engine()
            for table in DataLoader.REQUIRED_TABLES:
                if table == 'Destinos':
                    query = "SELECT DestinoID, nombre_completo, distancia_km, provinciaID FROM Destinos"
                    dfs[table] = pd.read_sql(query, engine)
                else:
                    dfs[table] = pd.read_sql_table(table, engine)
            
            # Cargar geo interno siempre
            if os.path.exists("data/raw/Provincias_geo.csv"):
                dfs['Provincias_geo'] = pd.read_csv("data/raw/Provincias_geo.csv", sep=',')
            return dfs
        except Exception as e:
            print(f"❌ Error SQL: {e}")
            return None