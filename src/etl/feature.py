import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from tqdm import tqdm

class FeatureEngineering:
    
    @staticmethod
    def create_master_dataset(dfs):
        print("\n\u001b[1;36m⚙️ Generando Dataset Maestro (Merges & Geocoding)...\u001b[0m")
        
        try:
            df_pedidos = dfs['Pedidos']
            df_lineas = dfs['LineasPedido']
            df_prod = dfs['Productos']
            df_dest = dfs['Destinos']
            
            # --- 1. NORMALIZACIÓN ---
            if 'provinciaID' in df_dest.columns:
                df_dest.rename(columns={'provinciaID': 'ProvinciaID'}, inplace=True)
            
            # Convertimos IDs a string '01', '02'... para asegurar cruce
            df_dest['ProvinciaID'] = df_dest['ProvinciaID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(2)

            # --- 2. MERGES ---
            df_master = pd.merge(df_pedidos, df_lineas, on='PedidoID', how='inner')
            df_master = pd.merge(df_master, df_prod, on='ProductoID', how='left')
            
            if 'Peso' in df_master.columns:
                df_master['Peso_Total_Kg'] = df_master['Cantidad'] * df_master['Peso']
            else:
                df_master['Peso_Total_Kg'] = df_master['Cantidad'] * 1.0 

            df_final = df_master.groupby('PedidoID').agg({
                'Peso_Total_Kg': 'sum',
                'DestinoEntregaID': 'first',
                'FechaPedido': 'first',
                'Caducidad': 'min'
            }).reset_index()
            
            df_final = pd.merge(df_final, df_dest, left_on='DestinoEntregaID', right_on='DestinoID', how='left')
            
            # --- 3. GEOCODING HÍBRIDO (Cache + Internet) ---
            
            # Usar caché local (rápido)
            if 'Provincias_geo' in dfs:
                df_geo = dfs['Provincias_geo']
                df_geo['ProvinciaID'] = df_geo['ProvinciaID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(2)
                df_final = pd.merge(df_final, df_geo[['ProvinciaID', 'Latitud', 'Longitud']], on='ProvinciaID', how='left')
            else:
                df_final['Latitud'] = None
                df_final['Longitud'] = None

            # Buscar faltantes en Internet (Geocoding)
            missing = df_final['Latitud'].isna()
            num_missing = missing.sum()
            
            if num_missing > 0:
                print(f"   ⚠️ Faltan coordenadas para {num_missing} pedidos. Intentando geocoding...")
                
                # Necesitamos nombres. Si el usuario subió Provincias.csv, lo usamos.
                if 'Provincias' in dfs:
                    df_nombres = dfs['Provincias']
                    # Asegurar ID compatible
                    if 'ProvinciaID' in df_nombres.columns:
                         df_nombres['ProvinciaID'] = df_nombres['ProvinciaID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(2)
                    
                    # Traer nombre al dataset principal temporalmente
                    df_final = pd.merge(df_final, df_nombres[['ProvinciaID', 'nombre']], on='ProvinciaID', how='left', suffixes=('', '_new'))
                    
                    # Buscar coordenadas para los nombres únicos que faltan
                    # (Para no hacer 100 llamadas si solo faltan 2 provincias)
                    prov_faltantes = df_final[df_final['Latitud'].isna()]['nombre'].unique()
                    prov_faltantes = [p for p in prov_faltantes if pd.notna(p)]
                    
                    if prov_faltantes:
                        print(f"   🌍 Consultando OpenStreetMap para: {prov_faltantes}")
                        geolocator = Nominatim(user_agent="logistic_v1")
                        
                        for p_nombre in tqdm(prov_faltantes):
                            try:
                                loc = geolocator.geocode(f"{p_nombre}, Spain")
                                if loc:
                                    # Rellenar en el dataframe principal
                                    mask = (df_final['nombre'] == p_nombre) & (df_final['Latitud'].isna())
                                    df_final.loc[mask, 'Latitud'] = loc.latitude
                                    df_final.loc[mask, 'Longitud'] = loc.longitude
                            except Exception as e:
                                print(f"Err geocoding {p_nombre}: {e}")
                else:
                    print("   ❌ No se puede geocodificar: Falta 'Provincias.csv' con los nombres.")

            # Limpieza final
            if 'nombre_new' in df_final.columns: df_final.drop(columns=['nombre_new'], inplace=True)
            
            # Fechas
            if 'FechaPedido' in df_final.columns:
                df_final['FechaPedido'] = pd.to_datetime(df_final['FechaPedido'])
                df_final['Fecha_Limite_Entrega'] = df_final['FechaPedido'] + pd.to_timedelta(df_final['Caducidad'], unit='D')

            print(f"✅ Dataset Maestro: {len(df_final)} pedidos. (Sin coords: {df_final['Latitud'].isna().sum()})")
            return df_final
            
        except KeyError as e:
            print(f"❌ Error Feature Engineering: {e}")
            return None