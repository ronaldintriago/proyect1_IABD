import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

class FeatureEngineering:
    
    @staticmethod
    def create_master_dataset(dfs):
        print("\n\u001b[1;36m Generando Dataset Maestro (Merges & Geocoding)...\u001b[0m")
        
        try:
            df_pedidos = dfs['Pedidos']
            df_lineas = dfs['LineasPedido']
            df_prod = dfs['Productos']
            df_dest = dfs['Destinos']
            
            # --- 1. NORMALIZACIÓN ---
            if 'provinciaID' in df_dest.columns:
                df_dest.rename(columns={'provinciaID': 'ProvinciaID'}, inplace=True)
            
            df_dest['ProvinciaID'] = df_dest['ProvinciaID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(2)

            # --- 2. MERGES ---
            df_master = pd.merge(df_pedidos, df_lineas, on='PedidoID', how='inner')
            df_master = pd.merge(df_master, df_prod, on='ProductoID', how='left')
            
            if 'Peso' in df_master.columns:
                df_master['Peso_Total_Kg'] = df_master['Cantidad'] * df_master['Peso']
            else:
                df_master['Peso_Total_Kg'] = df_master['Cantidad'] * 1.0 

            # Agrupar por Pedido
            df_final = df_master.groupby('PedidoID').agg({
                'Peso_Total_Kg': 'sum',
                'DestinoEntregaID': 'first',
                'FechaPedido': 'first',
                'Caducidad': 'min',
                'TiempoFabricacionMedio': 'max'
            }).reset_index()
            
            df_final = pd.merge(df_final, df_dest, left_on='DestinoEntregaID', right_on='DestinoID', how='left')
            
            # --- 3. GEOCODING HÍBRIDO ---
            if 'Provincias_geo' in dfs:
                df_geo = dfs['Provincias_geo']
                df_geo['ProvinciaID'] = df_geo['ProvinciaID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(2)
                df_final = pd.merge(df_final, df_geo[['ProvinciaID', 'Latitud', 'Longitud']], on='ProvinciaID', how='left')
            else:
                df_final['Latitud'] = None; df_final['Longitud'] = None

            # Buscar faltantes
            missing_mask = df_final['Latitud'].isna()
            num_missing = missing_mask.sum()
            
            if num_missing > 0:
                print(f"   ⚠️ Faltan coordenadas para {num_missing} pedidos. Iniciando Geocoding...")
                
                if 'Provincias' in dfs:
                    df_nombres = dfs['Provincias']
                    if 'ProvinciaID' in df_nombres.columns:
                         df_nombres['ProvinciaID'] = df_nombres['ProvinciaID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(2)
                    
                    df_final = pd.merge(df_final, df_nombres[['ProvinciaID', 'nombre']], on='ProvinciaID', how='left', suffixes=('', '_new'))
                    
                    prov_faltantes = df_final[df_final['Latitud'].isna()]['nombre'].unique()
                    prov_faltantes = [p for p in prov_faltantes if pd.notna(p)]
                    
                    if len(prov_faltantes) > 0:
                        print(f"   Consultando API para {len(prov_faltantes)} provincias...")
                        geolocator = Nominatim(user_agent="logistic_ia_system")

                        for i, p_nombre in enumerate(prov_faltantes):
                            try:
                                if i % 5 == 0: print(f"      > Geocodificando: {p_nombre}...")
                                
                                loc = geolocator.geocode(f"{p_nombre}, Spain")
                                if loc:
                                    mask = (df_final['nombre'] == p_nombre) & (df_final['Latitud'].isna())
                                    df_final.loc[mask, 'Latitud'] = loc.latitude
                                    df_final.loc[mask, 'Longitud'] = loc.longitude
                                time.sleep(1)
                            except Exception as e:
                                print(f"Error geo {p_nombre}: {e}")
                else:
                    print("   ❌ Faltan coordenadas y no hay 'Provincias.csv' para buscarlas.")

            if 'nombre_new' in df_final.columns: df_final.drop(columns=['nombre_new'], inplace=True)
            
            # --- 4. CÁLCULO FECHAS ---
            if 'FechaPedido' in df_final.columns:
                df_final['FechaPedido'] = pd.to_datetime(df_final['FechaPedido'])
                
                # Rellenamos NaNs en tiempos por si acaso (fallback a 0 y 1 día)
                df_final['TiempoFabricacionMedio'] = df_final['TiempoFabricacionMedio'].fillna(0)
                df_final['Caducidad'] = df_final['Caducidad'].fillna(1)

                # Límite = Disponible + Caducidad
                df_final['Fecha_Limite_Entrega'] = df_final['FechaPedido'] + \
                                                   pd.to_timedelta(df_final['TiempoFabricacionMedio'] + 1, unit='D') + \
                                                   pd.to_timedelta(df_final['Caducidad'], unit='D')

            print(f"✅ Dataset Maestro: {len(df_final)} pedidos. (Sin coords: {df_final['Latitud'].isna().sum()})")
            return df_final
            
        except KeyError as e:
            print(f"❌ Error Feature Engineering: {e}")
            return None