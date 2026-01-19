import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.etl.db_loader import DataLoader
from src.etl.feature import FeatureEngineering
from src.controllers.clustering_runner import ClusteringRunner
from src.models.routing import RouteSolver
from src.config.fleet_config import FLEET_CONFIG, SIMULATION_START_DATE

class LogisticsController:
    
    @staticmethod
    def inicializar_sistema(modo_carga, archivos_usuario=None):
        """
        Orquesta TODO el flujo inicial:
        1. Carga (SQL/CSV/Manual)
        2. Feature Engineering
        3. Clustering Automático (IA)
        4. Routing Automático
        """
        print("\n" + "="*50)
        print("INICIANDO SISTEMA DE LOGÍSTICA")
        print("="*50)
        
        # 1. CARGA DE DATOS
        dfs_raw = None
        
        if modo_carga == 'manual_upload':
            if not archivos_usuario:
                return {"status": "error", "msg": "No se recibieron archivos para cargar."}
            dfs_raw = DataLoader.load_manual_buffers(archivos_usuario)
            
        elif modo_carga == 'sql':
            dfs_raw = DataLoader.load_from_sql()
            
        else:
            dfs_raw = DataLoader.load_from_csv()
            
        if not dfs_raw:
            return {"status": "error", "msg": "Fallo crítico en la carga de datos."}

        # 2. FEATURE ENGINEERING
        df_maestro = FeatureEngineering.create_master_dataset(dfs_raw)
        if df_maestro is None or df_maestro.empty:
            return {"status": "error", "msg": "Error generando Dataset Maestro (revisa los CSVs)."}
        
        # Guardamos backup procesado
        os.makedirs("data/processed", exist_ok=True)
        df_maestro.to_csv("data/processed/dataset_master.csv", index=False)

        # 3. CLUSTERING AUTOMÁTICO (SOLUCIÓN ÓPTIMA)
        print("\n🤖 Calculando Flota Óptima (K-Means)...")
        res_clustering = ClusteringRunner.run_automatic_optimal_solution(df_maestro)
        
        # 4. ROUTING AUTOMÁTICO
        print("\nGenerando Rutas GPS...")
        rutas_gps = LogisticsController._ejecutar_routing(res_clustering["accepted_df"])
        
        return {
            "status": "success",
            "clustering": res_clustering,
            "rutas": rutas_gps,
            "fleet_used": res_clustering['fleet_used']
        }

    @staticmethod
    def recalcular_con_flota_manual(user_fleet):
        """
        Se llama desde la interfaz cuando el usuario mueve los sliders de flota.
        """
        print(f"\nRECALCULO MANUAL: Flota {user_fleet}")
        
        # Cargamos el dataset maestro (ya generado en el inicio)
        path = "data/processed/dataset_master.csv"
        if not os.path.exists(path):
            return {"status": "error", "msg": "Faltan datos procesados. Reinicia la app."}
            
        df_maestro = pd.read_csv(path)
        
        # Clustering Manual
        res_clustering = ClusteringRunner.run_manual_fleet_analysis(df_maestro, user_fleet)
        
        # Routing (Solo de lo que ha entrado en la flota)
        rutas = LogisticsController._ejecutar_routing(res_clustering["accepted_df"])
        
        return {
            "status": "success",
            "clustering": res_clustering,
            "rutas": rutas,
            "fleet_used": user_fleet
        }

    @staticmethod
    def _ejecutar_routing(df_clustered):
        """
        Helper privado que itera sobre los clusters y llama al motor de rutas (RouteSolver).
        """
        if df_clustered is None or df_clustered.empty: 
            return []
        
        rutas = []
        clusters = df_clustered['cluster_id'].unique()
        
        # Bucle normal sin tqdm para evitar Broken Pipe
        for i, cid in enumerate(clusters):
            # Feedback simple en consola (opcional)
            print(f"   > Procesando Cluster {cid} ({i+1}/{len(clusters)})...")
            
            subset = df_clustered[df_clustered['cluster_id'] == cid]
            
            # Obtenemos info del vehículo asignado a este cluster
            vid = subset['tipoVehiculo_id'].iloc[0]
            v_specs = FLEET_CONFIG.get(vid, FLEET_CONFIG[1])
            
            try:
                # Llamada al motor de routing
                ruta, historial = RouteSolver.solve_route(
                    pedidos=subset,
                    velocidad_kmh=v_specs['velocidad_media_kmh'],
                    fecha_inicio=SIMULATION_START_DATE
                )
                
                if ruta:
                    rutas.append({
                        "cluster_id": cid, 
                        "vehiculo": v_specs['nombre'],
                        "ruta": ruta,
                        "carga": subset['Peso_Total_Kg'].sum(),
                        "audit_history": historial,
                        "coste": 0
                    })
            except Exception as e:
                print(f"[WARN] Error ruteando cluster {cid}: {e}")
                
        return rutas