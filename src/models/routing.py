import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt
from datetime import datetime, timedelta

class RouteSolver:
    def __init__(self, df_pedidos, vehicle_speed_kmh=50, max_hours=None, start_date_str=None):
        """
        start_date_str: Fecha de inicio de la simulación.
        """
        # 1. Normalización
        self.points = df_pedidos.copy()
        
        # --- FIX CRÍTICO: RESETEAR ÍNDICE ---
        # Esto evita el KeyError: 0, 2, etc. alineando los índices con las matrices numpy
        self.points.reset_index(drop=True, inplace=True)
        # ------------------------------------
        
        column_mapping = {
            'PedidoID': 'id',
            'Latitud': 'lat',
            'Longitud': 'lon',
            'vehiculo_nombre': 'nombre',
            'Fecha_Limite_Entrega': 'deadline_str'
        }
        # Solo renombramos si existen
        self.points.rename(columns=column_mapping, inplace=True)

        # 2. Configuración Física
        self.n_points = len(self.points)
        self.speed_km_min = vehicle_speed_kmh / 60.0 

        # 3. GESTIÓN DE FECHA DE INICIO
        if start_date_str:
            try:
                base_date = pd.to_datetime(start_date_str)
                self.start_time = base_date.replace(hour=8, minute=0, second=0, microsecond=0)
            except:
                print(f"⚠️ Formato de fecha inválido ({start_date_str}). Usando HOY.")
                self.start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        else:
            self.start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

        # Calcular minutos de deadline relativos
        if 'deadline_str' in self.points.columns:
            self.points['deadline_minutos'] = self.points.apply(self._calculate_deadline_minutes, axis=1)
        else:
            self.points['deadline_minutos'] = 99999999

        # Asegurar IDs
        if 'id' not in self.points.columns: 
            self.points['id'] = self.points.index 
        
        if 'nombre' not in self.points.columns: 
            self.points['nombre'] = "Cliente_" + self.points['id'].astype(str)
        
        # 4. Matrices
        if self.n_points > 0:
            self.dist_matrix, self.time_matrix = self._calculate_matrices()
        else:
            self.dist_matrix, self.time_matrix = [], []

    # ==========================================
    # MÉTODO ESTÁTICO PUENTE (PARA EL CONTROLLER)
    # ==========================================
    @staticmethod
    def solve_route(pedidos, velocidad_kmh, fecha_inicio=None):
        """
        Instancia la clase y devuelve la ruta formateada con datos originales.
        """
        if pedidos.empty:
            return []
            
        # Instanciamos con la fecha de simulación
        solver = RouteSolver(
            pedidos, 
            vehicle_speed_kmh=velocidad_kmh, 
            start_date_str=fecha_inicio
        )
        
        # Resolvemos (obtenemos IDs)
        ruta_ids, _ = solver.solve()
        
        # Reconstruimos los datos completos buscando en el DF original
        pedidos_dict = pedidos.to_dict('records')
        # Mapeo seguro PedidoID -> Datos
        id_to_data = {row.get('PedidoID'): row for row in pedidos_dict}
        
        ruta_ordenada_detallada = []
        for rid in ruta_ids:
            # Ojo: rid puede ser int o str, aseguramos coincidencia
            if rid in id_to_data:
                ruta_ordenada_detallada.append(id_to_data[rid])
            else:
                # Fallback por si acaso el ID era el índice antiguo
                pass 
        
        return ruta_ordenada_detallada

    # ==========================================
    # LÓGICA INTERNA
    # ==========================================

    def _calculate_deadline_minutes(self, row):
        try:
            if str(row.get('id')) == "0" or row.get('nombre') == "CENTRAL":
                return 99999999

            deadline_str = row['deadline_str']
            dt_obj = pd.to_datetime(deadline_str)
            
            delta = dt_obj - self.start_time
            minutes = delta.total_seconds() / 60.0
            return minutes
        except:
            return 99999999

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371
        try:
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            return R * c
        except ValueError:
            return 0 

    def _calculate_matrices(self):
        dist = np.zeros((self.n_points, self.n_points))
        time = np.zeros((self.n_points, self.n_points))
        coords = self.points[['lat', 'lon']].values
        
        for i in range(self.n_points):
            for j in range(self.n_points):
                if i != j:
                    d = self._haversine(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
                    dist[i][j] = d
                    if self.speed_km_min > 0:
                        time[i][j] = d / self.speed_km_min
        return dist, time

    def solve(self):
        if self.n_points <= 1: 
            return [], []
        return self._solve_long_haul_tachograph()

    def _solve_long_haul_tachograph(self):
        current_node = 0
        visited = [False] * self.n_points
        visited[0] = True
        
        accumulated_driving_time = 0 
        total_mission_time = 0       
        
        node_to_real_id = self.points['id'].to_dict()
        real_depot_id = node_to_real_id[0]
        
        final_route_ids = [real_depot_id]

        for _ in range(self.n_points - 1):
            best_next_node = -1
            min_dist = float('inf')
            
            for j in range(1, self.n_points):
                if not visited[j]:
                    dist_km = self.dist_matrix[current_node][j]
                    driving_minutes = self.time_matrix[current_node][j]
                    
                    sim_driving = accumulated_driving_time + driving_minutes
                    sim_total = total_mission_time + driving_minutes + 10 
                    
                    if sim_driving > 480: 
                        sim_total += 720 
                        sim_driving = driving_minutes 
                    
                    deadline = self.points.iloc[j]['deadline_minutos']
                    
                    if sim_total <= deadline:
                        if dist_km < min_dist:
                            min_dist = dist_km
                            best_next_node = j
                            next_accum_driving = sim_driving
                            next_total_time = sim_total
            
            if best_next_node != -1:
                visited[best_next_node] = True
                final_route_ids.append(node_to_real_id[best_next_node])
                current_node = best_next_node
                accumulated_driving_time = next_accum_driving
                total_mission_time = next_total_time
            else:
                break
        
        final_route_ids.append(real_depot_id)

        backlog_ids = []
        for idx, fue_visitado in enumerate(visited):
            if not fue_visitado and idx != 0: 
                real_id = node_to_real_id[idx]
                backlog_ids.append(real_id)

        return final_route_ids, backlog_ids