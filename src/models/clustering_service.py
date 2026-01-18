import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from geopy.distance import great_circle
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    from src.config.fleet_config import FLEET_CONFIG
except ImportError:
    FLEET_CONFIG = {} 

HUB_COORDS = (41.5381, 2.4447) 

class ClusteringService:
    def __init__(self, data):
        self.df = data.copy()
        self.sorted_fleet = sorted(FLEET_CONFIG.items(), key=lambda x: x[1]['capacidad_kg'])
        self.MAX_STOPS = 20
        self.HUB = HUB_COORDS

    def _calculate_estimated_cost(self, cluster_df, vehicle_id):
        specs = FLEET_CONFIG[vehicle_id]
        center_lat = cluster_df['Latitud'].mean()
        center_lon = cluster_df['Longitud'].mean()
        centroid = (center_lat, center_lon)
        
        dist_hub_km = great_circle(self.HUB, centroid).km * 2
        
        if len(cluster_df) > 1:
            avg_spread = np.mean([great_circle((r['Latitud'], r['Longitud']), centroid).km 
                                  for _, r in cluster_df.iterrows()])
            dist_internal_km = avg_spread * len(cluster_df) * 0.8
        else:
            dist_internal_km = 0
            
        total_km_est = dist_hub_km + dist_internal_km
        coste_fijo = specs['coste_fijo_por_viaje']
        coste_variable = total_km_est * specs['coste_variable_por_km']
        total_euros = coste_fijo + coste_variable
        
        return total_euros, total_km_est

    def _get_cheapest_vehicle_for_cluster(self, weight):
        valid_vehicles = []
        for v_id, specs in self.sorted_fleet:
            if weight <= specs['capacidad_kg']:
                valid_vehicles.append(v_id)
        
        if not valid_vehicles:
            return 99, "EXCESO", 999999 
            
        best_v_id = valid_vehicles[0]
        return best_v_id, FLEET_CONFIG[best_v_id]['nombre'], FLEET_CONFIG[best_v_id]['capacidad_kg']

    def run_optimal_clustering(self):
        """
        Calcula la flota ideal y devuelve EL DETALLE de las rutas óptimas.
        """
        print("   ...Analizando configuraciones de flota óptima...")
        
        total_weight = self.df['Peso_Total_Kg'].sum()
        min_k = max(int(np.ceil(total_weight / 25000)), int(np.ceil(len(self.df) / self.MAX_STOPS)), 1)
        
        best_solution_details = [] # Lista de diccionarios con info de cada ruta
        min_total_cost = float('inf')
        
        for k in range(min_k, min_k + 15):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(self.df[['Latitud', 'Longitud']])
            
            temp_df = self.df.copy()
            temp_df['cluster'] = labels
            
            current_solution_cost = 0
            feasible = True
            current_iteration_details = []
            
            for cid in range(k):
                cluster_data = temp_df[temp_df['cluster'] == cid]
                w = cluster_data['Peso_Total_Kg'].sum()
                stops = len(cluster_data)
                
                if stops > self.MAX_STOPS:
                    feasible = False; break
                
                v_id, v_name, v_cap = self._get_cheapest_vehicle_for_cluster(w)
                
                if v_id == 99:
                    feasible = False; break
                
                cost_eur, dist_km = self._calculate_estimated_cost(cluster_data, v_id)
                current_solution_cost += cost_eur
                
                current_iteration_details.append({
                    'cluster_id': cid + 1,
                    'vehiculo': v_name,
                    'peso': w,
                    'paradas': stops,
                    'coste': cost_eur,
                    'capacidad_max': v_cap
                })
            
            if feasible and current_solution_cost < min_total_cost:
                min_total_cost = current_solution_cost
                best_solution_details = current_iteration_details
        
        return best_solution_details, min_total_cost

    def run_user_fleet_clustering(self, user_fleet_counts):
        
        available_vehicles = []
        for v_id, count in user_fleet_counts.items():
            for _ in range(count): available_vehicles.append(v_id)
        
        vehicle_objs = []
        for v_id in available_vehicles:
            specs = FLEET_CONFIG[v_id]
            vehicle_objs.append({'id': v_id, 'cap': specs['capacidad_kg'], 'name': specs['nombre']})
        
        vehicle_objs.sort(key=lambda x: x['cap'], reverse=True)
        K = len(vehicle_objs)
        if K == 0: return None, None, 0
        if K > len(self.df): K = len(self.df)

        kmeans = KMeans(n_clusters=K, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(self.df[['Latitud', 'Longitud']])
        distances = np.min(kmeans.transform(self.df[['Latitud', 'Longitud']]), axis=1)
        
        self.df['cluster_id'] = clusters
        self.df['distancia_centroide'] = distances
        cluster_weights = self.df.groupby('cluster_id')['Peso_Total_Kg'].sum().sort_values(ascending=False)
        
        df_accepted_list = []
        df_discarded_list = []
        total_cost_user = 0
        
        used_routes_details = [] 

        for i, (cluster_id, total_weight) in enumerate(cluster_weights.items()):
            if i < len(vehicle_objs):
                vehicle = vehicle_objs[i]
                cluster_orders = self.df[self.df['cluster_id'] == cluster_id].sort_values('distancia_centroide')
                
                accepted = []
                curr_w = 0; curr_s = 0
                for _, order in cluster_orders.iterrows():
                    if curr_s >= self.MAX_STOPS:
                        df_discarded_list.append(order); continue
                    if curr_w + order['Peso_Total_Kg'] <= vehicle['cap']:
                        accepted.append(order)
                        curr_w += order['Peso_Total_Kg']; curr_s += 1
                    else:
                        df_discarded_list.append(order)
                
                if accepted:
                    df_acc = pd.DataFrame(accepted)
                    df_acc['tipoVehiculo_id'] = vehicle['id']
                    df_acc['vehiculo_nombre'] = vehicle['name']
                    df_acc['cluster_id'] = i + 1
                    df_accepted_list.append(df_acc)
                    
                    cost_eur, _ = self._calculate_estimated_cost(df_acc, vehicle['id'])
                    total_cost_user += cost_eur
                    
                    # Guardar resumen para devolver
                    used_routes_details.append({
                        'cluster_id': i + 1,
                        'vehiculo': vehicle['name'],
                        'peso': curr_w,
                        'paradas': curr_s,
                        'coste': cost_eur,
                        'capacidad_max': vehicle['cap']
                    })
            else:
                 # Resto clusters descartados enteros
                 rest_orders = self.df[self.df['cluster_id'] == cluster_id]
                 for _, r in rest_orders.iterrows(): df_discarded_list.append(r)

        if df_accepted_list: df_final_acc = pd.concat(df_accepted_list)
        else: df_final_acc = pd.DataFrame(columns=self.df.columns)
            
        if df_discarded_list: df_final_disc = pd.concat([pd.DataFrame(df_discarded_list)]) if isinstance(df_discarded_list[0], pd.Series) else pd.DataFrame(df_discarded_list)
        else: df_final_disc = pd.DataFrame(columns=self.df.columns)
            
        return df_final_acc, df_final_disc, total_cost_user, used_routes_details

    def print_detailed_comparison(self, user_details, ideal_details, user_cost, ideal_cost, n_discarded):
        """
        Imprime una comparación detallada ruta a ruta.
        """
        print("\n" + "="*80)
        print(f"📊 REPORTE COMPARATIVO FINAL")
        print("="*80)
        
        # --- SECCIÓN USUARIO ---
        print(f"\n🚛 TU ESTRATEGIA (Coste: {user_cost:.2f} €)")
        if not user_details:
            print("   (No se generaron rutas válidas)")
        else:
            print(f"   {'Ruta':<5} | {'Vehículo':<20} | {'Carga (Kg)':<12} | {'Paradas':<8} | {'Ocupación'}")
            print("   " + "-"*70)
            for r in user_details:
                ocupacion = (r['peso'] / r['capacidad_max']) * 100
                print(f"   #{r['cluster_id']:<4} | {r['vehiculo']:<20} | {r['peso']:<6.0f}/{r['capacidad_max']:<5} | {r['paradas']:<8} | {ocupacion:.1f}%")
        
        if n_discarded > 0:
            print(f"   ⚠️  PEDIDOS DESCARTADOS: {n_discarded} (Capacidad insuficiente)")
        else:
            print("   ✅ Todos los pedidos servidos.")

        # --- SECCIÓN IDEAL ---
        print("-" * 80)
        print(f"\n💡 ESTRATEGIA ÓPTIMA IA (Coste: {ideal_cost:.2f} €)")
        print(f"   {'Ruta':<5} | {'Vehículo':<20} | {'Carga (Kg)':<12} | {'Paradas':<8} | {'Ocupación'}")
        print("   " + "-"*70)
        
        # Agrupamos por tipo para contar flota recomendada
        fleet_counts = {}
        
        for r in ideal_details:
            ocupacion = (r['peso'] / r['capacidad_max']) * 100
            print(f"   #{r['cluster_id']:<4} | {r['vehiculo']:<20} | {r['peso']:<6.0f}/{r['capacidad_max']:<5} | {r['paradas']:<8} | {ocupacion:.1f}%")
            
            fleet_counts[r['vehiculo']] = fleet_counts.get(r['vehiculo'], 0) + 1

        print("="*80)
        
        # --- CONCLUSIONES ---
        ahorro = user_cost - ideal_cost
        if n_discarded > 0:
            print(f"🔴 CONCLUSIÓN: Tu flota NO ES VIABLE (Faltan {n_discarded} pedidos).")
        elif ahorro > 50:
            print(f"🟠 CONCLUSIÓN: Tu flota sirve, pero pierdes {ahorro:.2f} € por viaje.")
        else:
            print(f"🟢 CONCLUSIÓN: ¡Excelente! Tu flota es casi tan eficiente como la ideal.")
            
        print("\n📦 FLOTA RECOMENDADA:")
        for v, c in fleet_counts.items():
            print(f"   • {c} x {v}")
        print("\n")