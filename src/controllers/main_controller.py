import pandas as pd
import sys
import os
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.models.routing import RouteSolver
from src.controllers.clustering_runner import ClusteringRunner
from src.config.fleet_config import FLEET_CONFIG, SIMULATION_START_DATE

class LogisticsController:
    
    @staticmethod
    def load_master_data():
        """Carga datos del ETL"""
        path = "data/processed/dataset_master.csv"
        if not os.path.exists(path): return None
        try:
            df = pd.read_csv(path)
            # Legacy fix
            if 'coordenadas' in df.columns and 'Latitud' not in df.columns:
                 df[['Latitud', 'Longitud']] = df['coordenadas'].str.split(',', expand=True).astype(float)
            return df
        except: return None

    @staticmethod
    def generar_arranque_automatico():
        """
        ESTO SE LLAMA AL ABRIR STREAMLIT.
        Calcula la solución óptima directamente sin preguntar nada.
        """
        print("\n⚡ INICIO AUTOMÁTICO: Calculando solución óptima...")
        df = LogisticsController.load_master_data()
        if df is None: return {"status": "error", "msg": "Faltan datos"}

        # 1. Clustering Automático (Busca la flota perfecta)
        res_clustering = ClusteringRunner.run_automatic_optimal_solution(df)
        
        # 2. Routing Automático
        rutas = LogisticsController._ejecutar_routing(res_clustering["accepted_df"])
        
        return {
            "status": "success",
            "type": "optimal",
            "clustering": res_clustering,
            "rutas": rutas
        }

    @staticmethod
    def recalcular_con_flota_manual(user_fleet):
        """
        ESTO SE LLAMA CUANDO EL USUARIO TOCA LOS SLIDERS EN STREAMLIT.
        """
        print(f"\n🔧 RECALCULO MANUAL: Flota {user_fleet}")
        df = LogisticsController.load_master_data()
        if df is None: return {"status": "error"}

        # 1. Clustering Manual (Usa lo que dice el usuario)
        res_clustering = ClusteringRunner.run_manual_fleet_analysis(df, user_fleet)
        
        # 2. Routing (Solo de lo que cupo)
        rutas = LogisticsController._ejecutar_routing(res_clustering["accepted_df"])
        
        return {
            "status": "success",
            "type": "manual",
            "clustering": res_clustering,
            "rutas": rutas
        }

    @staticmethod
    def _ejecutar_routing(df_clustered):
        """Helper privado para no repetir código"""
        if df_clustered.empty: return []
        
        rutas = []
        clusters = df_clustered['cluster_id'].unique()
        
        # Usamos tqdm para ver progreso en terminal
        for cid in tqdm(clusters, desc="Generando rutas GPS"):
            subset = df_clustered[df_clustered['cluster_id'] == cid]
            vid = subset['tipoVehiculo_id'].iloc[0]
            v_specs = FLEET_CONFIG[vid]
            
            try:
                ruta = RouteSolver.solve_route(subset, v_specs['velocidad_media_kmh'], fecha_inicio = SIMULATION_START_DATE)
                if ruta:
                    rutas.append({
                        "cluster_id": cid, 
                        "vehiculo": v_specs['nombre'],
                        "ruta": ruta,
                        "carga": subset['Peso_Total_Kg'].sum()
                    })
            except Exception as e:
                print(f"[WARN] Error ruteando cluster {cid}: {e}")
                
        return rutas