import pandas as pd

class FeatureEngineering:
    
    @staticmethod
    def create_master_dataset(dfs):
        print("\u001b[1;36m⚙️ Generando Dataset Maestro (Merges & Features)...\u001b[0m")
        
        try:
            df_pedidos = dfs['Pedidos']
            df_lineas = dfs['LineasPedido']
            df_prod = dfs['Productos']
            df_dest = dfs['Destinos']
            
            # --- CORRECCIÓN DE NOMBRES (NORMALIZACIÓN) ---
            # Aseguramos que provinciaID sea ProvinciaID para que cuadre con todo
            if 'provinciaID' in df_dest.columns:
                df_dest.rename(columns={'provinciaID': 'ProvinciaID'}, inplace=True)
            
            # 1. Merge Pedidos + Lineas
            df_master = pd.merge(df_pedidos, df_lineas, on='PedidoID', how='inner')
            
            # 2. Merge + Productos
            df_master = pd.merge(df_master, df_prod, on='ProductoID', how='left')
            
            # 3. Calcular Pesos
            if 'Peso' in df_master.columns:
                df_master['Peso_Total_Kg'] = df_master['Cantidad'] * df_master['Peso']
            else:
                df_master['Peso_Total_Kg'] = df_master['Cantidad'] * 1.0 

            # 4. Agrupar por Pedido
            df_final = df_master.groupby('PedidoID').agg({
                'Peso_Total_Kg': 'sum',
                'DestinoEntregaID': 'first',
                'FechaPedido': 'first',
                'Caducidad': 'min'
            }).reset_index()
            
            # 5. Merge + Destinos
            # Aquí fallaba antes. Ahora estamos seguros de que DestinoID existe.
            df_final = pd.merge(df_final, df_dest, left_on='DestinoEntregaID', right_on='DestinoID', how='left')
            
            # 6. GESTIÓN DE COORDENADAS (Desde Provincias_geo)
            if 'Provincias_geo' in dfs:
                df_geo = dfs['Provincias_geo']
                
                # Merge por ProvinciaID para asignar lat/lon aproximada
                if 'ProvinciaID' in df_final.columns and 'ProvinciaID' in df_geo.columns:
                    # Asegurar tipos iguales (string vs int)
                    df_final['ProvinciaID'] = df_final['ProvinciaID'].astype(str).str.zfill(2)
                    df_geo['ProvinciaID'] = df_geo['ProvinciaID'].astype(str).str.zfill(2)
                    
                    df_final = pd.merge(df_final, df_geo[['ProvinciaID', 'Latitud', 'Longitud']], on='ProvinciaID', how='left')
            
            # Limpieza final de coordenadas si vinieran en string
            if 'coordenadas' in df_final.columns and 'Latitud' not in df_final.columns:
                df_final[['Latitud', 'Longitud']] = df_final['coordenadas'].str.split(',', expand=True).astype(float)
            
            # 7. Calcular Fecha Límite
            if 'FechaPedido' in df_final.columns and 'Caducidad' in df_final.columns:
                df_final['FechaPedido'] = pd.to_datetime(df_final['FechaPedido'])
                df_final['Fecha_Limite_Entrega'] = df_final['FechaPedido'] + pd.to_timedelta(df_final['Caducidad'], unit='D')

            print(f"✅ Dataset Maestro creado: {len(df_final)} pedidos.")
            return df_final
            
        except KeyError as e:
            print(f"❌ Error en Merges: Falta columna/tabla {e}")
            # Importante: Imprimir columnas disponibles para depurar
            if 'Destinos' in dfs:
                print(f"   Columnas en Destinos: {dfs['Destinos'].columns.tolist()}")
            return None