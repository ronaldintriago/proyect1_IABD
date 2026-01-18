import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt
from datetime import datetime, timedelta

class RouteSolver:
    def __init__(self, df_pedidos, vehicle_speed_kmh=50, max_hours=None, start_date_str=None):
        self.points = df_pedidos.copy()
        self.points.reset_index(drop=True, inplace=True)
        
        column_mapping = {
            'PedidoID': 'id',
            'Latitud': 'lat',
            'Longitud': 'lon',
            'vehiculo_nombre': 'nombre',
            'Fecha_Limite_Entrega': 'deadline_str'
        }
        self.points.rename(columns=column_mapping, inplace=True)

        self.n_points = len(self.points)
        self.speed_km_min = vehicle_speed_kmh / 60.0 

        if start_date_str:
            try:
                base_date = pd.to_datetime(start_date_str)
                self.start_time = base_date.replace(hour=8, minute=0, second=0, microsecond=0)
            except:
                self.start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        else:
            self.start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

        if 'deadline_str' in self.points.columns:
            self.points['deadline_minutos'] = self.points.apply(self._calculate_deadline_minutes, axis=1)
        else:
            self.points['deadline_minutos'] = 99999999

        if 'id' not in self.points.columns: self.points['id'] = self.points.index 
        if 'nombre' not in self.points.columns: self.points['nombre'] = "Cliente_" + self.points['id'].astype(str)
        
        if self.n_points > 0:
            self.dist_matrix, self.time_matrix = self._calculate_matrices()
        else:
            self.dist_matrix, self.time_matrix = [], []

    def _calculate_deadline_minutes(self, row):
        try:
            if str(row.get('id')) == "0" or row.get('nombre') == "CENTRAL": return 99999999
            dt = pd.to_datetime(row['deadline_str'])
            return (dt - self.start_time).total_seconds() / 60.0
        except: return 99999999

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371
        try:
            dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
            return R * 2 * asin(sqrt(a))
        except: return 0 

    def _calculate_matrices(self):
        dist = np.zeros((self.n_points, self.n_points))
        time = np.zeros((self.n_points, self.n_points))
        coords = self.points[['lat', 'lon']].values
        for i in range(self.n_points):
            for j in range(self.n_points):
                if i != j:
                    d = self._haversine(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
                    dist[i][j] = d
                    if self.speed_km_min > 0: time[i][j] = d / self.speed_km_min
        return dist, time

    @staticmethod
    def solve_route(pedidos, velocidad_kmh, fecha_inicio=None):
        """
        Retorna: (ruta_detallada, historial_pasos)
        """
        if pedidos.empty: return [], []
            
        solver = RouteSolver(pedidos, vehicle_speed_kmh=velocidad_kmh, start_date_str=fecha_inicio)
        
        # Obtenemos ruta final IDs y el historial de pasos
        ruta_ids, _, history_steps = solver.solve()
        
        # Reconstrucción de datos
        pedidos_dict = pedidos.to_dict('records')
        id_to_data = {row.get('PedidoID'): row for row in pedidos_dict}
        
        # Ruta Final Detallada
        ruta_final = []
        for rid in ruta_ids:
            if rid in id_to_data: ruta_final.append(id_to_data[rid])
            
        # Historial Detallado (Para la animación)
        # Convertimos [[id1], [id1, id2]...] a objetos completos
        history_detailed = []
        for step_idx, step_ids in enumerate(history_steps):
            step_data = []
            for rid in step_ids:
                if rid in id_to_data:
                    d = id_to_data[rid].copy()
                    d['step_index'] = step_idx
                    step_data.append(d)
            history_detailed.extend(step_data)
            
        return ruta_final, history_detailed

    def solve(self):
        if self.n_points <= 1: return [], [], []
        return self._solve_long_haul_tachograph()

    def _solve_long_haul_tachograph(self):
        current_node = 0
        visited = [False] * self.n_points
        visited[0] = True
        
        accum_driving = 0; total_mission = 0
        
        node_to_real_id = self.points['id'].to_dict()
        real_depot_id = node_to_real_id[0]
        
        final_route_ids = [real_depot_id]
        
        # --- Historial de Pasos ---
        history = []
        # Paso 0: Solo el depósito
        history.append([real_depot_id]) 

        for _ in range(self.n_points - 1):
            best_next = -1; min_dist = float('inf')
            next_accum_drv = 0; next_total_time = 0
            
            for j in range(1, self.n_points):
                if not visited[j]:
                    d_km = self.dist_matrix[current_node][j]
                    t_min = self.time_matrix[current_node][j]
                    
                    sim_drv = accum_driving + t_min
                    sim_tot = total_mission + t_min + 10 
                    
                    if sim_drv > 480: 
                        sim_tot += 720; sim_drv = t_min 
                    
                    if sim_tot <= self.points.iloc[j]['deadline_minutos']:
                        if d_km < min_dist:
                            min_dist = d_km; best_next = j
                            next_accum_drv = sim_drv; next_total_time = sim_tot
            
            if best_next != -1:
                visited[best_next] = True
                real_next_id = node_to_real_id[best_next]
                final_route_ids.append(real_next_id)
                current_node = best_next
                accum_driving = next_accum_drv
                total_mission = next_total_time
                
                # --- Guardamos la foto del momento ---
                history.append(list(final_route_ids))
            else:
                break
        
        final_route_ids.append(real_depot_id)
        # Vuelta a casa
        history.append(list(final_route_ids))

        backlog = [node_to_real_id[i] for i, v in enumerate(visited) if not v and i != 0]

        return final_route_ids, backlog, history