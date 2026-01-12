import pandas as pd
import sys
import os
from tqdm import tqdm  # <--- ¡AQUÍ ESTABA EL FALTANTE!

# Ajuste de path para que Python encuentre los módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.etl.db_loader import DataLoader
from src.etl.feature import FeatureEngineering
from src.controllers.clustering_runner import ClusteringRunner
from src.models.routing import RouteSolver
from src.config.fleet_config import FLEET_CONFIG, SIMULATION_START_DATE

class LogisticsController:
    
    @staticmethod
    def inicializar_sistema(modo_carga):
        """
        Orquesta TODO el flujo inicial:
        1. Carga (SQL/CSV)
        2. Feature Engineering
        3. Clustering Automático (IA)
        4. Routing Automático
        """
        print("\n" + "="*50)
        print("🚀 INICIANDO SISTEMA DE LOGÍSTICA")
        print("="*50)
        
        # 1. CARGA
        if modo_carga == 'csv':
            dfs_raw = DataLoader.load_from_csv()
        else:
            dfs_raw = DataLoader.load_from_sql()
            
        if not dfs_raw:
            return {"status": "error", "msg": "Fallo crítico en la carga de datos."}

        # 2. FEATURE ENGINEERING
        df_maestro = FeatureEngineering.create_master_dataset(dfs_raw)
        if df_maestro is None or df_maestro.empty:
            return {"status": "error", "msg": "Error generando Dataset Maestro."}
        
        # Guardamos backup por si acaso
        os.makedirs("data/processed", exist_ok=True)
        df_maestro.to_csv("data/processed/dataset_master.csv", index=False)

        # 3. CLUSTERING AUTOMÁTICO (SOLUCIÓN ÓPTIMA)
        print("\n🤖 Calculando Flota Óptima...")
        res_clustering = ClusteringRunner.run_automatic_optimal_solution(df_maestro)
        
        # 4. ROUTING AUTOMÁTICO
        print("\n📍 Generando Rutas GPS...")
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
        Se llama cuando el usuario cambia los sliders en Streamlit.
        """
        print(f"\n🔧 RECALCULO MANUAL: Flota {user_fleet}")
        
        # Cargamos el dataset maestro (ya generado en el paso 1)
        path = "data/processed/dataset_master.csv"
        if not os.path.exists(path):
            return {"status": "error", "msg": "Faltan datos procesados."}
            
        df_maestro = pd.read_csv(path)
        
        # Clustering Manual
        res_clustering = ClusteringRunner.run_manual_fleet_analysis(df_maestro, user_fleet)
        
        # Routing (Solo de lo que cupo)
        rutas = LogisticsController._ejecutar_routing(res_clustering["accepted_df"])
        
        return {
            "status": "success",
            "clustering": res_clustering,
            "rutas": rutas,
            "fleet_used": user_fleet
        }

    @staticmethod
    def _ejecutar_routing(df_clustered):
        """Helper privado para calcular rutas GPS"""
        if df_clustered is None or df_clustered.empty: 
            return []
        
        rutas = []
        clusters = df_clustered['cluster_id'].unique()
        
        # Barra de progreso en terminal
        for cid in tqdm(clusters, desc="Ruteando clusters"):
            subset = df_clustered[df_clustered['cluster_id'] == cid]
            
            # Obtenemos info del vehículo asignado
            vid = subset['tipoVehiculo_id'].iloc[0]
            v_specs = FLEET_CONFIG.get(vid, FLEET_CONFIG[1]) # Fallback seguro
            
            try:
                # Llamada al motor de routing
                ruta = RouteSolver.solve_route(
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
                        # Recuperamos el coste estimado que calculó el clustering para este cluster
                        # (Opcional, si no lo tienes a mano, se recalcula o se deja a 0)
                        "coste": 0 
                    })
            except Exception as e:
                print(f"[WARN] Error ruteando cluster {cid}: {e}")
                
        return rutas