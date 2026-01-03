

import pandas as pd
from src.data.db_loader import DataLoader
from src.models.routing import RouteSolver
from src.models.clustering_service import ClusteringService
from src.config.fleet_config import FLEET_CONFIG

# Configuración de Flota 


class LogisticsController:
    
    @staticmethod
    def ejecutar_calculo_diario(flota_usuario):
        """
        Orquesta todo el proceso: Datos -> Clustering -> Routing.
        
        Args:
            flota_usuario (dict): {vehiculo_id: cantidad}. Ej: {1: 2, 3: 1}
        """
        print("\n" + "="*60)
        print("🚀 INICIANDO EJECUCIÓN DEL CONTROLADOR PRINCIPAL")
        print("="*60)

        # ------------------------------------------------------
        # PASO 1: CARGAR DATOS (ETL)
        # ------------------------------------------------------
        print("📂 1. Cargando datos maestros...")
        df_vista_maestra = DataLoader.load_all_data() 
        
        if df_vista_maestra is None or df_vista_maestra.empty:
            return {"error": "No se pudieron cargar los datos."}       
        # ------------------------------------------------------
        # PASO 2: CLUSTERING (TU PARTE)
        # ------------------------------------------------------
        print("🤖 2. Ejecutando Clustering (Asignación de Flota)...")
        
        # Instanciamos tu servicio
        cluster_service = ClusteringService(df_vista_maestra)
        
        # A. Ejecutamos con la flota REAL del usuario
        # Esto devuelve los pedidos que SÍ caben (accepted) y los que NO (discarded)
        df_accepted, df_discarded, user_cost, user_routes_details = cluster_service.run_user_fleet_clustering(flota_usuario)
        
        # B. Ejecutamos la comparativa IDEAL (para el reporte final)
        ideal_routes_details, ideal_cost = cluster_service.run_optimal_clustering()
        
        print(f"   ✅ Clustering finalizado. Pedidos aceptados para ruta: {len(df_accepted)}")
        
        # --- MOCK TEMPORAL (Simulamos que tu compañero ya hizo su trabajo) ---
        # Esto lo borras cuando él te pase su código
        df_clustered = df_vista_maestra.copy()
        df_clustered['ClusterID'] = 1  # Todos al vehículo 1
        df_clustered['TipoVehiculoID'] = 4 # Tipo Tráiler
        # -------------------------------------------------------------------

        # 3. ROUTING (Tu trabajo)
        resultados_finales = []
        backlog = []

        ids_vehiculos = df_clustered['ClusterID'].unique()

        for vehiculo_id in ids_vehiculos:
            # A. Cortamos el trozo de tarta
            subset = df_clustered[df_clustered['ClusterID'] == vehiculo_id].copy()
            
            # B. Miramos configuración
            tipo_id = subset.iloc[0]['TipoVehiculoID']
            config_vehiculo = FLEET_CONFIG.get(tipo_id, FLEET_CONFIG[2]) # Default a Tipo 2
            
            # C. Ejecutamos Solver
            try:
                solver = RouteSolver(
                    subset, 
                    vehicle_speed_kmh=config_vehiculo["velocidad"],
                    max_hours=8
                )
                ruta = solver.solve()
                
                if ruta:
                    resultados_finales.append({
                        "VehiculoID": vehiculo_id,
                        "Tipo": config_vehiculo["nombre"],
                        "Ruta": ruta,  # Lista ordenada de IDs
                        "Pedidos": len(ruta) - 2 # Restamos Depósito salida y llegada
                    })
                else:
                    # Si falla, todo al backlog
                    backlog.extend(subset['PedidoID'].tolist())
                    
            except Exception as e:
                print(f"Error en vehículo {vehiculo_id}: {e}")
                backlog.extend(subset['PedidoID'].tolist())

        # 4. RETORNO PARA LA VISTA
        return {
            "rutas": resultados_finales,
            "backlog": backlog,
            "total_pedidos": len(df_vista_maestra)
        }
        
    @staticmethod
    def calcular_flota_perfecta():
        """
        Calcula la composición ideal de vehículos para Backlog = 0.
        Estrategia: Iterar incrementando K (clusters) hasta que todo encaje.
        """
        # 1. Cargar Datos
        df_vista, _ = DataLoader.get_data_from_csv_files("data/csv_files")
        total_kilos = df_vista['Cantidad'].sum()
        
        # 2. Estimación Inicial (Heurística)
        # Empezamos probando con el mínimo de Tráilers posibles para llevar todo el peso
        capacidad_max_trailer = FLEET_CONFIG[4]["capacidad"] # 25.000
        k_inicial = int(total_kilos / capacidad_max_trailer) + 1
        
        # Límite de seguridad para no buclear infinito
        k_maximo = len(df_vista)  
        
        print(f"🔄 Iniciando búsqueda de flota ideal. K inicial: {k_inicial}")

        flota_ideal_resultado = None

        # 3. Bucle Iterativo
        for k in range(k_inicial, k_maximo):
            # A. Simulamos Clustering con 'k' vehículos
            # (Tu compañero debe permitirte pasarle el número de clusters deseado 'n_clusters')
            # df_clustered = ClusterEngine.generar_clusters_k_means(df_vista, n_clusters=k)
            
            # --- MOCK (Simulación mientras no tienes a tu compañero) ---
            df_clustered = df_vista.copy()
            # Simulamos que dividimos equitativamente en k grupos
            df_clustered['ClusterID'] = pd.qcut(df_clustered.index, k, labels=[f"V_{i}" for i in range(k)])
            # ---------------------------------------------------------

            rutas_validas = []
            backlog_total = []
            flota_sugerida = {} # Para contar: 2 Trailers, 1 Furgoneta...

            ids_vehiculos = df_clustered['ClusterID'].unique()

            # B. Evaluamos cada clúster generado
            for vid in ids_vehiculos:
                subset = df_clustered[df_clustered['ClusterID'] == vid].copy()
                carga_cluster = subset['Cantidad'].sum()
                
                # C. ASIGNACIÓN DINÁMICA DE VEHÍCULO
                # Aquí decidimos qué vehículo compramos según la carga del clúster
                if carga_cluster <= FLEET_CONFIG[2]["capacidad"]: # Cabe en Furgoneta
                    tipo_asignado = 2
                elif carga_cluster <= FLEET_CONFIG[4]["capacidad"]: # Cabe en Tráiler
                    tipo_asignado = 4
                else:
                    # Si el clúster pesa más que un Tráiler, este 'k' no vale.
                    # El clustering ha fallado en equilibrar. Forzamos siguiente iteración.
                    backlog_total.append("OVERWEIGHT") 
                    break 

                config = FLEET_CONFIG[tipo_asignado]
                
                # D. Routing (Validar tiempos)
                try:
                    solver = RouteSolver(
                        subset, 
                        vehicle_speed_kmh=config["velocidad"],
                        max_hours=8
                    )
                    ruta = solver.solve()
                    
                    if ruta:
                        rutas_validas.append({
                            "VehiculoID": vid,
                            "Tipo": config["nombre"],
                            "Carga": carga_cluster,
                            "Ruta": ruta
                        })
                        # Contamos para el resumen
                        nombre_tipo = config["nombre"]
                        flota_sugerida[nombre_tipo] = flota_sugerida.get(nombre_tipo, 0) + 1
                    else:
                        backlog_total.extend(subset['PedidoID'].tolist())
                        
                except:
                    backlog_total.append("ERROR")

            # 4. Verificación de Éxito
            if len(backlog_total) == 0:
                # ¡ÉXITO! Hemos encontrado una configuración donde cabe todo y llega a tiempo
                flota_ideal_resultado = {
                    "resumen_flota": flota_sugerida, # Ej: {"Tráiler": 2, "Furgoneta": 1}
                    "rutas": rutas_validas,
                    "iteraciones": k
                }
                break # Salimos del bucle
            else:
                print(f"   K={k} insuficiente (Backlog: {len(backlog_total)}). Probando K={k+1}...")

        return flota_ideal_resultado