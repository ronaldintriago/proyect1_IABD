import pandas as pd
import sys
import os
import math
from tqdm import tqdm

# Ajuste de paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.data.db_loader import DataLoader
from src.models.routing import RouteSolver
from src.models.clustering_service import ClusteringService
from src.config.fleet_config import FLEET_CONFIG

# --- CONFIGURACIÓN DE FECHA ---
FECHA_SIMULACION = "2025-12-15" 

class LogisticsController:
    
    @staticmethod
    def ejecutar_calculo_diario(flota_usuario):
        print("\n" + "="*60, flush=True)
        print(f"🚀 INICIANDO MODO MANUAL | Fecha Simulación: {FECHA_SIMULACION}", flush=True)
        print("="*60, flush=True)

        # 1. CARGAR DATOS MAESTROS (dataset_master.csv)
        print("📂 Cargando datos maestros...", flush=True)
        path_master = "data/processed/dataset_master.csv"
        
        # Búsqueda robusta del maestro
        if not os.path.exists(path_master):
            if os.path.exists("dataset_master.csv"): path_master = "dataset_master.csv"
            else: return {"error": "Falta dataset_master.csv. Por favor súbelo o ejecútalo."}

        try:
            df_vista_maestra = pd.read_csv(path_master)
        except Exception as e:
            return {"error": str(e)}
       
        # 2. CLUSTERING
        print("🤖 Ejecutando Clustering (Asignación por Peso)...", flush=True)
        cluster_service = ClusteringService(df_vista_maestra)
        df_accepted, df_discarded_weight, _, _ = cluster_service.run_user_fleet_clustering(flota_usuario)
        
        print(f"   -> Clustering OK. Aceptados: {len(df_accepted)} | Descartados Peso: {len(df_discarded_weight)}", flush=True)

        # --- 💾 GUARDADO AUTOMÁTICO DE CSV (NUEVO) ---
        # Esto crea el archivo 'dataset_clustered.csv' para que el mapa pueda leerlo después.
        try:
            output_path = "data/processed/dataset_clustered.csv"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df_accepted.to_csv(output_path, index=False)
            print(f"💾 Archivo intermedio generado: {output_path}", flush=True)
        except Exception as e:
            print(f"⚠️ No se pudo guardar el archivo intermedio: {e}", flush=True)
        # ---------------------------------------------

        # 3. ROUTING
        print("🚚 Calculando Rutas (Larga Distancia)...", flush=True)
        
        resultados_finales = []
        backlog_tiempo_ids = []

        if not df_accepted.empty:
            ids_clusters = df_accepted['cluster_id'].unique()
            barra_progreso = tqdm(ids_clusters, desc="Ruteando", unit="veh")
            
            for cluster_id in barra_progreso:
                subset = df_accepted[df_accepted['cluster_id'] == cluster_id].copy()
                tipo_id = subset.iloc[0]['tipoVehiculo_id']
                config = FLEET_CONFIG.get(int(tipo_id))
                
                # Inyección Depósito
                deposito = pd.DataFrame([{
                    'PedidoID': 0,                
                    'cluster_id': cluster_id,     
                    'tipoVehiculo_id': tipo_id,
                    'Latitud': 41.5381,           
                    'Longitud': 2.4447,
                    'vehiculo_nombre': 'CENTRAL',
                    'Fecha_Limite_Entrega': '2099-12-31', 
                    'Peso_Total_Kg': 0            
                }])
                df_routing = pd.concat([deposito, subset], ignore_index=True)

                try:
                    solver = RouteSolver(
                        df_routing, 
                        vehicle_speed_kmh=config["velocidad_media_kmh"], 
                        max_hours=1000, 
                        start_date_str=FECHA_SIMULACION
                    )
                    
                    ruta, olvidados = solver.solve()
                    
                    if olvidados:
                        backlog_tiempo_ids.extend(olvidados)

                    if ruta and len(ruta) > 2:
                        resultados_finales.append({
                            "VehiculoID": int(cluster_id),
                            "Tipo": config["nombre"],
                            "Ruta": ruta,
                            "Pedidos": len(ruta) - 2,
                            "Carga": subset['Peso_Total_Kg'].sum()
                        })
                    
                except Exception as e:
                    print(f"Error Routing Cluster {cluster_id}: {e}", flush=True)
                    backlog_tiempo_ids.extend(subset['PedidoID'].tolist())
        
        # 4. RESUMEN
        total_backlog_count = len(df_discarded_weight) + len(backlog_tiempo_ids)
        print("\n" + "-"*60, flush=True)
        print(f"🏁 FINALIZADO. Rutas OK: {len(resultados_finales)} | Backlog Total: {total_backlog_count}", flush=True)
        print(f"   - Por Peso (Clustering): {len(df_discarded_weight)}", flush=True)
        print(f"   - Por Caducidad (Routing): {len(backlog_tiempo_ids)}", flush=True)
        print("-"*60 + "\n", flush=True)

        return {
            "rutas": resultados_finales,
            "backlog_capacidad": df_discarded_weight,
            "backlog_tiempo": backlog_tiempo_ids,
            "total_pedidos": len(df_vista_maestra)
        }

    @staticmethod
    def calcular_flota_perfecta():
        """
        MODO AUTOMÁTICO
        """
        print("\n" + "="*60, flush=True)
        print(f"🔮 INICIANDO CÁLCULO FLOTA PERFECTA | Fecha: {FECHA_SIMULACION}", flush=True)
        print("="*60, flush=True)

        if os.path.exists("data/processed/dataset_master.csv"):
             df_vista_maestra = pd.read_csv("data/processed/dataset_master.csv")
        else:
             return {"error": "Falta dataset_master.csv"}

        total_kilos = df_vista_maestra['Peso_Total_Kg'].sum()
        cap_trailer = FLEET_CONFIG[4]["capacidad_kg"]
        num_trailers_inicial = math.ceil(total_kilos / cap_trailer)
        
        flota_actual = {4: num_trailers_inicial} 
        cluster_service = ClusteringService(df_vista_maestra)

        flota_optima = None
        iteracion = 0
        max_iteraciones = 12 

        with tqdm(total=max_iteraciones, desc="Optimizando") as pbar:
            while iteracion < max_iteraciones:
                iteracion += 1
                pbar.set_description(f"Iteración {iteracion} | Flota: {flota_actual}")
                
                df_accepted, df_discarded, _, _ = cluster_service.run_user_fleet_clustering(flota_actual)

                backlog_tiempo = []
                rutas_validas = []

                if not df_accepted.empty:
                    clusters = df_accepted['cluster_id'].unique()
                    
                    for cluster_id in clusters: 
                        subset = df_accepted[df_accepted['cluster_id'] == cluster_id].copy()
                        tipo_id = subset.iloc[0]['tipoVehiculo_id']
                        config = FLEET_CONFIG.get(int(tipo_id))

                        deposito = pd.DataFrame([{
                            'PedidoID': 0, 'cluster_id': cluster_id, 'tipoVehiculo_id': tipo_id,
                            'Latitud': 41.5381, 'Longitud': 2.4447, 'vehiculo_nombre': 'CENTRAL',
                            'Fecha_Limite_Entrega': '2099-12-31', 'Peso_Total_Kg': 0            
                        }])
                        df_routing = pd.concat([deposito, subset], ignore_index=True)

                        try:
                            solver = RouteSolver(
                                df_routing, 
                                vehicle_speed_kmh=config["velocidad_media_kmh"],
                                max_hours=1000,
                                start_date_str=FECHA_SIMULACION
                            )
                            # --- CAPTURAMOS BACKLOG ---
                            ruta, olvidados = solver.solve()
                            
                            if olvidados:
                                backlog_tiempo.extend(olvidados)

                            if ruta and len(ruta) > 2:
                                rutas_validas.append({
                                    "VehiculoID": int(cluster_id),
                                    "Tipo": config["nombre"],
                                    "Carga": subset['Peso_Total_Kg'].sum(),
                                    "Ruta": ruta
                                })
                        except:
                            backlog_tiempo.extend(subset['PedidoID'].tolist())

                total_backlog = len(df_discarded) + len(backlog_tiempo)

                if total_backlog == 0:
                    pbar.write(f"✅ ¡EUREKA! Solución encontrada.")
                    flota_optima = {
                        "resumen_flota": flota_actual.copy(),
                        "rutas": rutas_validas,
                        "iteraciones": iteracion
                    }
                    break
                else:
                    pbar.write(f"❌ Fallo (Backlog: {total_backlog}). Incrementando...")
                    pbar.update(1)
                    
                    peso_backlog = df_discarded['Peso_Total_Kg'].sum() if not df_discarded.empty else 0
                    if peso_backlog > 1500 or len(backlog_tiempo) > 4:
                        flota_actual[4] = flota_actual.get(4, 0) + 1
                    else:
                        flota_actual[2] = flota_actual.get(2, 0) + 1
        
        return flota_optima


def main_test_modelo():
        # Prueba rápida del modo manual
        flota_test = {1:5, 2: 6, 4:1}
        LogisticsController.ejecutar_calculo_diario(flota_test)

# --- BLOQUE DE TEST (EJECUCIÓN DIRECTA) ---
if __name__ == "__main__":
    main_test_modelo()
    