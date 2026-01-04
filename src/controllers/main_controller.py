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

class LogisticsController:
    
    @staticmethod
    def ejecutar_calculo_diario(flota_usuario):
        """
        MODO MANUAL: Rutas con recursos finitos.
        """
        print("\n" + "="*60)
        print("🚀 INICIANDO MODO MANUAL (FLOTA USUARIO)")
        print("="*60)

        # 1. CARGAR DATOS
        print("📂 Cargando datos maestros...")
        try:
            if os.path.exists("src/data/datasets/dataset_master.csv"):
                 df_vista_maestra = pd.read_csv("src/data/datasets/dataset_master.csv")
            else:
                 return {"error": "Falta dataset_master.csv. Ejecuta el ETL primero."}
        except Exception as e:
            return {"error": str(e)}
       
        # 2. CLUSTERING
        print("🤖 Ejecutando Clustering (Asignación por Peso)...")
        cluster_service = ClusteringService(df_vista_maestra)
        df_accepted, df_discarded_weight, _, _ = cluster_service.run_user_fleet_clustering(flota_usuario)
        
        print(f"   -> Aceptados Clustering: {len(df_accepted)} | Backlog Peso: {len(df_discarded_weight)}")

        # 3. ROUTING
        print("🚚 Calculando Rutas Óptimas...")
        
        resultados_finales = []
        backlog_tiempo_ids = []

        if not df_accepted.empty:
            ids_clusters = df_accepted['cluster_id'].unique()
            barra_progreso = tqdm(ids_clusters, desc="Ruteando", unit="vehiculo")
            
            for cluster_id in barra_progreso:
                # A. OBTENER CLIENTES DEL CLÚSTER
                subset_clientes = df_accepted[df_accepted['cluster_id'] == cluster_id].copy()
                
                # Obtener configuración vehículo
                tipo_id = subset_clientes.iloc[0]['tipoVehiculo_id']
                config = FLEET_CONFIG.get(int(tipo_id))
                
                if not config: continue
                barra_progreso.set_postfix({"Tipo": config['nombre']})

                # ==========================================================
                # B. INYECCIÓN DEL DEPÓSITO (CENTRAL MATARÓ) - CRÍTICO
                # ==========================================================
                # Creamos la fila 0 que representa el almacén
                deposito = pd.DataFrame([{
                    'PedidoID': 0,                
                    'cluster_id': cluster_id,     
                    'tipoVehiculo_id': tipo_id,
                    'Latitud': 41.5381,           # COORDENADAS MATARÓ
                    'Longitud': 2.4447,
                    'vehiculo_nombre': 'CENTRAL',
                    'Fecha_Limite_Entrega': '2099-12-31', 
                    'Peso_Total_Kg': 0            
                }])

                # Unimos: Depósito primero + Clientes después
                df_routing_input = pd.concat([deposito, subset_clientes], ignore_index=True)

                # ==========================================================
                # C. LLAMADA AL ROUTING
                # ==========================================================
                try:
                    
                    solver = RouteSolver(
                        df_routing_input, 
                        vehicle_speed_kmh=config["velocidad_media_kmh"],
                        max_hours=8 
                    )
                    ruta = solver.solve()
                    
                    if ruta:
                        resultados_finales.append({
                            "VehiculoID": int(cluster_id),
                            "Tipo": config["nombre"],
                            "Ruta": ruta,
                            "Pedidos": len(ruta) - 2, # -2 porque hay salida y llegada a central
                            "Carga": subset_clientes['Peso_Total_Kg'].sum()
                        })
                    else:
                        # Si ruta es None, es imposible llegar a tiempo
                        backlog_tiempo_ids.extend(subset_clientes['PedidoID'].tolist())
                except Exception as e:
                    print(f"Error en cluster {cluster_id}: {e}")
                    backlog_tiempo_ids.extend(subset_clientes['PedidoID'].tolist())
        
        # 4. RESUMEN
        print("\n" + "-"*60)
        print(f"🏁 FINALIZADO. Rutas OK: {len(resultados_finales)} | Backlog Total: {len(df_discarded_weight) + len(backlog_tiempo_ids)}")
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
        MODO AUTOMÁTICO
        """
        print("\n" + "="*60)
        print("🔮 INICIANDO CÁLCULO DE FLOTA PERFECTA")
        print("="*60)

        if os.path.exists("src/data/datasets/dataset_master.csv"):
             df_vista_maestra = pd.read_csv("src/data/datasets/dataset_master.csv")
        else:
             return {"error": "Falta dataset_master.csv"}

        total_kilos = df_vista_maestra['Peso_Total_Kg'].sum()
        cap_trailer = FLEET_CONFIG[4]["capacidad_kg"]
        num_trailers_inicial = math.ceil(total_kilos / cap_trailer)
        
        flota_actual = {4: num_trailers_inicial} 
        cluster_service = ClusteringService(df_vista_maestra)

        flota_optima = None
        iteracion = 0
        max_iteraciones = 10 

        with tqdm(total=max_iteraciones, desc="Optimizando") as pbar:
            while iteracion < max_iteraciones:
                iteracion += 1
                pbar.set_description(f"Iteración {iteracion} | Flota: {flota_actual}")
                
                # A. Clustering
                df_accepted, df_discarded, _, _ = cluster_service.run_user_fleet_clustering(flota_actual)

                # B. Routing Check
                backlog_tiempo = []
                rutas_validas = []

                if not df_accepted.empty:
                    clusters = df_accepted['cluster_id'].unique()
                    
                    for cluster_id in clusters: 
                        subset_clientes = df_accepted[df_accepted['cluster_id'] == cluster_id].copy()
                        tipo_id = subset_clientes.iloc[0]['tipoVehiculo_id']
                        config = FLEET_CONFIG.get(int(tipo_id))

                        # --- INYECCIÓN DEPÓSITO TAMBIÉN AQUÍ ---
                        deposito = pd.DataFrame([{
                            'PedidoID': 0, 'cluster_id': cluster_id, 'tipoVehiculo_id': tipo_id,
                            'Latitud': 41.5381, 'Longitud': 2.4447, 'vehiculo_nombre': 'CENTRAL',
                            'Fecha_Limite_Entrega': '2099-12-31', 'Peso_Total_Kg': 0            
                        }])
                        df_routing_input = pd.concat([deposito, subset_clientes], ignore_index=True)
                        # ---------------------------------------

                        try:
                            # Aumentado max_hours a 24 para pruebas
                            solver = RouteSolver(
                                df_routing_input, 
                                vehicle_speed_kmh=config["velocidad_media_kmh"],
                                max_hours=24
                            )
                            ruta = solver.solve()

                            if ruta:
                                rutas_validas.append({
                                    "VehiculoID": int(cluster_id),
                                    "Tipo": config["nombre"],
                                    "Carga": subset_clientes['Peso_Total_Kg'].sum(),
                                    "Ruta": ruta
                                })
                            else:
                                backlog_tiempo.extend(subset_clientes['PedidoID'].tolist())
                        except:
                            backlog_tiempo.extend(subset_clientes['PedidoID'].tolist())

                # C. Evaluar
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
                    # Estrategia incremento
                    pbar.write(f"❌ Fallo (Backlog: {total_backlog}). Incrementando...")
                    peso_backlog = df_discarded['Peso_Total_Kg'].sum() if not df_discarded.empty else 0
                    if peso_backlog > 1500 or len(backlog_tiempo) > 2:
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
    