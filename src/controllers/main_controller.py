import pandas as pd
import sys
import os
import math
from tqdm import tqdm 

# Ajuste de paths para importaciones
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.data.db_loader import DataLoader
from src.models.routing import RouteSolver
from src.models.clustering_service import ClusteringService
from src.config.fleet_config import FLEET_CONFIG

class LogisticsController:
    
    @staticmethod
    def ejecutar_calculo_diario(flota_usuario):
        """
        MODO MANUAL: Rutas con recursos finitos definidos por el usuario.
        """
        print("\n" + "="*60)
        print("🚀 INICIANDO MODO MANUAL (FLOTA USUARIO)")
        print("="*60)

        # 1. CARGAR DATOS
        print("📂 Cargando datos maestros...")
        try:
            # Intentamos cargar el CSV maestro limpio
            if os.path.exists("src/data/datasets/dataset_master.csv"):
                 df_vista_maestra = pd.read_csv("src/data/datasets/dataset_master.csv")
            else:
                 # Fallback: Usar el loader (ajusta según tu lógica real de carga)
                 return {"error": "Falta dataset_master.csv. Ejecuta el ETL primero."}
        except Exception as e:
            return {"error": str(e)}
       
        # 2. CLUSTERING (CAPACIDAD)
        print("🤖 Ejecutando Clustering (Asignación por Peso)...")
        cluster_service = ClusteringService(df_vista_maestra)
        
        # Llamada al servicio de tu compañero
        df_accepted, df_discarded_weight, _, _ = cluster_service.run_user_fleet_clustering(flota_usuario)
        
        print(f"   -> Aceptados para ruteo: {len(df_accepted)}")
        print(f"   -> Descartados por Peso (Backlog 1): {len(df_discarded_weight)}")

        # 3. ROUTING (TIEMPO)
        print("🚚 Calculando Secuencias Óptimas...")
        
        resultados_finales = []
        backlog_tiempo_ids = []

        if not df_accepted.empty:
            ids_clusters = df_accepted['cluster_id'].unique()

            # Barra de progreso visual
            barra_progreso = tqdm(ids_clusters, desc="Ruteando Vehículos", unit="ruta")
            
            for cluster_id in barra_progreso:
                subset = df_accepted[df_accepted['cluster_id'] == cluster_id].copy()
                
                # Obtener configuración del vehículo
                tipo_id = subset.iloc[0]['tipoVehiculo_id']
                config = FLEET_CONFIG.get(int(tipo_id))
                
                if not config: continue

                # Info visual en la barra
                barra_progreso.set_postfix({"Vehículo": config['nombre'], "ID": cluster_id})

                try:
                    # Instanciar Solver
                    solver = RouteSolver(
                        subset, 
                        vehicle_speed_kmh=config["velocidad_media_kmh"], # Clave exacta de fleet_config.py
                        max_hours=8
                    )
                    ruta = solver.solve()
                    
                    if ruta:
                        resultados_finales.append({
                            "VehiculoID": int(cluster_id),
                            "Tipo": config["nombre"],
                            "Ruta": ruta,
                            "Pedidos": len(ruta) - 2, # Restar depósitos
                            "Carga": subset['Peso_Total_Kg'].sum()
                        })
                    else:
                        # Si devuelve None es Infeasible por tiempo
                        backlog_tiempo_ids.extend(subset['PedidoID'].tolist())
                except Exception as e:
                    # Error inesperado cuenta como backlog
                    backlog_tiempo_ids.extend(subset['PedidoID'].tolist())
        
        # 4. RESUMEN
        total_backlog_count = len(df_discarded_weight) + len(backlog_tiempo_ids)
        print("\n" + "-"*60)
        print(f"🏁 FINALIZADO. Rutas OK: {len(resultados_finales)} | Backlog Total: {total_backlog_count}")
        print("-"*60)

        return {
            "rutas": resultados_finales,
            "backlog_capacidad": df_discarded_weight,
            "backlog_tiempo": backlog_tiempo_ids,
            "total_pedidos": len(df_vista_maestra)
        }

    @staticmethod
    def calcular_flota_perfecta():
        """
        MODO AUTOMÁTICO: Encuentra la flota ideal incrementando recursos hasta Backlog=0.
        """
        print("\n" + "="*60)
        print("🔮 INICIANDO CÁLCULO DE FLOTA PERFECTA")
        print("="*60)

        # Cargar Datos
        if os.path.exists("src/data/datasets/dataset_master.csv"):
             df_vista_maestra = pd.read_csv("src/data/datasets/dataset_master.csv")
        else:
             return {"error": "Falta dataset_master.csv"}

        # Estimación Inicial (Heurística)
        total_kilos = df_vista_maestra['Peso_Total_Kg'].sum()
        cap_trailer = FLEET_CONFIG[4]["capacidad_kg"]
        num_trailers_inicial = math.ceil(total_kilos / cap_trailer)
        
        flota_actual = {4: num_trailers_inicial} 
        cluster_service = ClusteringService(df_vista_maestra)

        flota_optima = None
        iteracion = 0
        max_iteraciones = 12 

        print(f"⚖️  Carga Total: {total_kilos} Kg -> Inicio: {num_trailers_inicial} Tráilers")

        # Barra de progreso general para iteraciones
        with tqdm(total=max_iteraciones, desc="Buscando Solución Ideal") as pbar:
            
            while iteracion < max_iteraciones:
                iteracion += 1
                pbar.set_description(f"Iteración {iteracion} | Probando: {flota_actual}")
                
                # A. Clustering
                df_accepted, df_discarded, _, _ = cluster_service.run_user_fleet_clustering(flota_actual)

                # B. Routing
                backlog_tiempo = []
                rutas_validas = []

                if not df_accepted.empty:
                    clusters = df_accepted['cluster_id'].unique()
                    
                    for cluster_id in clusters: 
                        subset = df_accepted[df_accepted['cluster_id'] == cluster_id].copy()
                        tipo_id = subset.iloc[0]['tipoVehiculo_id']
                        config = FLEET_CONFIG.get(int(tipo_id))

                        try:
                            solver = RouteSolver(
                                subset, 
                                vehicle_speed_kmh=config["velocidad_media_kmh"],
                                max_hours=8
                            )
                            ruta = solver.solve()

                            if ruta:
                                rutas_validas.append({
                                    "VehiculoID": int(cluster_id),
                                    "Tipo": config["nombre"],
                                    "Carga": subset['Peso_Total_Kg'].sum(),
                                    "Ruta": ruta
                                })
                            else:
                                backlog_tiempo.extend(subset['PedidoID'].tolist())
                        except:
                            backlog_tiempo.extend(subset['PedidoID'].tolist())

                # C. Evaluar Resultado
                total_backlog = len(df_discarded) + len(backlog_tiempo)

                if total_backlog == 0:
                    pbar.write(f"✅ ¡EUREKA! Solución encontrada en iteración {iteracion}")
                    pbar.update(max_iteraciones - iteracion + 1) # Completar barra
                    flota_optima = {
                        "resumen_flota": flota_actual.copy(),
                        "rutas": rutas_validas,
                        "iteraciones": iteracion
                    }
                    break
                else:
                    pbar.write(f"❌ Fallo (Backlog: {total_backlog}). Incrementando flota...")
                    pbar.update(1)
                    
                    # Estrategia de incremento inteligente
                    peso_backlog = df_discarded['Peso_Total_Kg'].sum() if not df_discarded.empty else 0
                    
                    # Si sobra mucho peso o fallan muchos por tiempo, metemos camión grande
                    if peso_backlog > 1500 or len(backlog_tiempo) > 4:
                        flota_actual[4] = flota_actual.get(4, 0) + 1
                    else:
                        # Ajuste fino con furgoneta
                        flota_actual[2] = flota_actual.get(2, 0) + 1
        
        return flota_optima
    
def main_test_modelo():
        # Prueba rápida del modo manual
        flota_test = {1: 5, 2: 2, 4: 1}
        LogisticsController.ejecutar_calculo_diario(flota_test)

# --- BLOQUE DE TEST (EJECUCIÓN DIRECTA) ---
if __name__ == "__main__":
    main_test_modelo()
    