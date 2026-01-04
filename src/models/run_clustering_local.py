import pandas as pd
import os
import sys
from src.models.clustering_service import ClusteringService
from src.config.fleet_config import FLEET_CONFIG

# RUTAS
INPUT_CSV = "data/processed/dataset_master.csv"
OUTPUT_CLUSTERED = "data/processed/dataset_clustered.csv"
OUTPUT_DISCARDED = "data/processed/pedidos_descartados.csv"

def limpiar_archivos_previos():
    for f in [OUTPUT_CLUSTERED, OUTPUT_DISCARDED]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except: pass

def pedir_flota_usuario():
    print("\n🚛 CONFIGURACIÓN DE TU FLOTA")
    print("Por favor, indica cuántos vehículos tienes:")
    user_fleet = {}
    for v_id, specs in FLEET_CONFIG.items():
        while True:
            try:
                cant = int(input(f"   > Cantidad de '{specs['nombre']}' ({specs['capacidad_kg']}kg): "))
                if cant < 0: raise ValueError
                user_fleet[v_id] = cant
                break
            except ValueError:
                print("   ❌ Introduce un número positivo.")
    if sum(user_fleet.values()) == 0:
        print("⚠️ Flota vacía. Saliendo..."); sys.exit()
    return user_fleet

def main_cluster():
    limpiar_archivos_previos()

    if not os.path.exists(INPUT_CSV):
        print(f"❌ Error: No encuentro {INPUT_CSV}")
        return

    print(f"📂 Cargando {INPUT_CSV}...")
    try:
        df = pd.read_csv(INPUT_CSV, sep=',')
    except:
        df = pd.read_csv(INPUT_CSV, sep=';')

    if 'coordenadas' in df.columns and 'Latitud' not in df.columns:
        df[['Latitud', 'Longitud']] = df['coordenadas'].str.split(',', expand=True).astype(float)

    # 1. INPUT DE USUARIO
    user_fleet = pedir_flota_usuario()

    service = ClusteringService(df)
    
    # 2. EJECUCIÓN FLOTA USUARIO (Ahora devuelve detalles_rutas también)
    df_accepted, df_discarded, user_cost, user_routes_details = service.run_user_fleet_clustering(user_fleet)

    # 3. EJECUCIÓN FLOTA IDEAL (Ahora devuelve detalles_rutas también)
    print("\n🤖 Calculando comparativa óptima...")
    ideal_routes_details, ideal_cost = service.run_optimal_clustering()

    # 4. IMPRIMIR COMPARACIÓN DETALLADA
    service.print_detailed_comparison(
        user_routes_details, 
        ideal_routes_details, 
        user_cost, 
        ideal_cost, 
        len(df_discarded)
    )

    # 5. GUARDAR ARCHIVOS
    os.makedirs(os.path.dirname(OUTPUT_CLUSTERED), exist_ok=True)
    
    cols_export = ['PedidoID', 'cluster_id', 'tipoVehiculo_id', 'vehiculo_nombre', 
                   'Latitud', 'Longitud', 'Peso_Total_Kg', 'Fecha_Limite_Entrega']
    final_cols = [c for c in cols_export if c in df_accepted.columns]
    
    if not df_accepted.empty:
        df_accepted[final_cols].to_csv(OUTPUT_CLUSTERED, index=False)
        print(f"💾 Dataset generado para Routing: {OUTPUT_CLUSTERED}")
    
    if not df_discarded.empty:
        df_discarded.to_csv(OUTPUT_DISCARDED, index=False)
        print(f"💾 Descartados guardados en: {OUTPUT_DISCARDED}")

if __name__ == "__main__":
    main_cluster()