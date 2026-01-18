import pandas as pd
import os
from src.models.clustering_service import ClusteringService
from src.config.fleet_config import FLEET_CONFIG

# Rutas de salida
OUTPUT_CLUSTERED = "data/processed/dataset_clustered.csv"
OUTPUT_DISCARDED = "data/processed/pedidos_descartados.csv"

class ClusteringRunner:
    
    @staticmethod
    def _limpiar_archivos():
        for f in [OUTPUT_CLUSTERED, OUTPUT_DISCARDED]:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass

    @staticmethod
    def _guardar_resultados(df_accepted, df_discarded):
        """Helper para guardar CSVs"""
        os.makedirs(os.path.dirname(OUTPUT_CLUSTERED), exist_ok=True)
        cols_export = ['PedidoID', 'cluster_id', 'tipoVehiculo_id', 'vehiculo_nombre', 
                       'Latitud', 'Longitud', 'Peso_Total_Kg', 'Fecha_Limite_Entrega']
        final_cols = [c for c in cols_export if c in df_accepted.columns]
        
        if not df_accepted.empty:
            df_accepted[final_cols].to_csv(OUTPUT_CLUSTERED, index=False)
        
        if not df_discarded.empty:
            df_discarded.to_csv(OUTPUT_DISCARDED, index=False)

    @staticmethod
    def run_manual_fleet_analysis(df_maestro, user_fleet_config):
        """MODO MANUAL: El usuario dice qué flota tiene."""
        ClusteringRunner._limpiar_archivos()
        service = ClusteringService(df_maestro)
        
        # 1. Ejecutamos con la flota impuesta
        df_acc, df_disc, cost, details = service.run_user_fleet_clustering(user_fleet_config)
        
        # 2. Guardamos y Retornamos
        ClusteringRunner._guardar_resultados(df_acc, df_disc)
        
        return {
            "mode": "manual",
            "accepted_df": df_acc,
            "discarded_df": df_disc,
            "metrics": {"cost": cost},
            "details": details,
            "fleet_used": user_fleet_config
        }

    @staticmethod
    def run_automatic_optimal_solution(df_maestro):
        """
        MODO AUTOMÁTICO:
        1. La IA calcula la flota ideal teórica.
        2. Convertimos esa recomendación en una configuración de flota real.
        3. Ejecutamos el clustering normal con esa flota 'perfecta' para generar las rutas.
        """
        ClusteringRunner._limpiar_archivos()
        service = ClusteringService(df_maestro)
        
        print("[INFO] 🧠 Calculando Flota Óptima Automática...")
        
        # 1. Obtener la recomendación teórica
        ideal_details, ideal_cost = service.run_optimal_clustering()
        
        # 2. Traducir "Detalles de Ruta" a "Conteo de Flota" para poder re-ejecutar
        # Generamos: {4: 2} (ID del Trailer: Cantidad)
        
        # Mapa inverso: Nombre -> ID
        name_to_id = {v['nombre']: k for k, v in FLEET_CONFIG.items()}
        
        optimal_fleet_config = {}
        for route in ideal_details:
            v_name = route['vehiculo']
            v_id = name_to_id.get(v_name)
            if v_id:
                optimal_fleet_config[v_id] = optimal_fleet_config.get(v_id, 0) + 1
        
        print(f"[INFO] 💡 Flota Óptima Detectada: {optimal_fleet_config}")

        # 3. Re-ejecutar el clustering estándar usando esta flota perfecta
        # Hacemos esto para obtener el DataFrame 'df_accepted' formateado igual que en el modo manual
        df_acc, df_disc, cost, details = service.run_user_fleet_clustering(optimal_fleet_config)
        
        # 4. Guardamos
        ClusteringRunner._guardar_resultados(df_acc, df_disc)
        
        return {
            "mode": "optimal",
            "accepted_df": df_acc,
            "discarded_df": df_disc,
            "metrics": {"cost": cost},
            "details": details,
            "fleet_used": optimal_fleet_config
        }