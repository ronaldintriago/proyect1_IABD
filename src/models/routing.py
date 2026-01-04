import pulp
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt

class RouteSolver:
    def __init__(self, df_pedidos, vehicle_speed_kmh=50, max_hours=8):
        # 1. Normalización de Nombres
        self.points = df_pedidos.copy()
        
        column_mapping = {
            'PedidoID': 'id',
            'Latitud': 'lat',
            'Longitud': 'lon',
            'vehiculo_nombre': 'nombre',
            'Fecha_Limite_Entrega': 'deadline_date'
        }
        self.points.rename(columns=column_mapping, inplace=True)

        # 2. Gestión de Deadlines
        self.max_minutes = max_hours * 60
        if 'deadline_minutos' not in self.points.columns:
            self.points['deadline_minutos'] = self.max_minutes

        # Asegurar IDs y Nombres
        if 'id' not in self.points.columns:
             self.points['id'] = self.points.index 
        if 'nombre' not in self.points.columns:
            self.points['nombre'] = "Cliente_" + self.points['id'].astype(str)

        # 3. Configuración Física
        self.n_points = len(self.points)
        self.nodes = range(self.n_points)
        self.speed_km_min = vehicle_speed_kmh / 60.0 
        
        # 4. Matrices
        if self.n_points > 0:
            self.dist_matrix, self.time_matrix = self._calculate_matrices()
        else:
            self.dist_matrix, self.time_matrix = [], []

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
        """
        Método inteligente que decide qué algoritmo usar según el tamaño del problema.
        """
        # Safety Check
        if self.n_points <= 1: return []

        # UMBRAL DE DECISIÓN:
        # - Menos de 16 puntos: Usamos MATEMÁTICAS EXACTAS (PuLP). Es lento pero perfecto.
        # - Más de 16 puntos: Usamos HEURÍSTICA (Vecino Más Cercano). Es instantáneo.
        if self.n_points < 16:
            return self._solve_exact_pulp()
        else:
            return self._solve_heuristic_nearest_neighbor()

    def _solve_exact_pulp(self):
        """
        Solver Exacto (MILP) usando PuLP.
        """
        prob = pulp.LpProblem("VRP_Routing", pulp.LpMinimize)
        x = pulp.LpVariable.dicts("x", (self.nodes, self.nodes), cat='Binary')
        t = pulp.LpVariable.dicts("t", self.nodes, lowBound=0, upBound=self.max_minutes)
        
        prob += t[0] == 0 # Inicio

        # Función Objetivo
        prob += pulp.lpSum([self.dist_matrix[i][j] * x[i][j] 
                            for i in self.nodes for j in self.nodes if i != j])

        # Restricciones de flujo
        for i in range(1, self.n_points): 
            prob += pulp.lpSum([x[j][i] for j in self.nodes if i != j]) == 1
            prob += pulp.lpSum([x[i][j] for j in self.nodes if i != j]) == 1

        prob += pulp.lpSum([x[0][j] for j in range(1, self.n_points)]) == 1
        prob += pulp.lpSum([x[i][0] for i in range(1, self.n_points)]) == 1

        # MTZ (Tiempo)
        M = 10000 
        for i in self.nodes:
            for j in range(1, self.n_points):
                if i != j:
                    prob += t[j] >= t[i] + 10 + self.time_matrix[i][j] - M*(1-x[i][j])

        # Ventanas de tiempo
        for i in range(1, self.n_points):
            deadline = self.points.iloc[i]['deadline_minutos']
            prob += t[i] <= deadline

        # LIMITAMOS A 30 SEGUNDOS POR SI ACASO
        prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))

        if pulp.LpStatus[prob.status] in ['Optimal', 'Feasible']:
            return self._reconstruct_route(x)
        else:
            return None

    def _solve_heuristic_nearest_neighbor(self):
        """
        Algoritmo Voraz (Greedy): "Ve al cliente más cercano que aún no has visitado".
        Es O(N^2) en vez de O(N!), es decir, tarda 0.01 segundos en vez de 20 minutos.
        """
        visited = [False] * self.n_points
        route_indices = [0] # Empezamos en depósito
        visited[0] = True
        
        current_node = 0
        current_time = 0
        
        # Mapeo inverso ID
        if 'id' in self.points.columns:
             real_depot_id = self.points.iloc[0]['id']
        else:
             real_depot_id = 0
        
        final_route_ids = [real_depot_id]
        node_to_real_id = self.points['id'].to_dict()

        # Bucle principal: buscar el siguiente más cercano
        for _ in range(self.n_points - 1):
            best_next_node = -1
            min_dist = float('inf')
            
            for j in range(1, self.n_points):
                if not visited[j]:
                    dist = self.dist_matrix[current_node][j]
                    travel_time = self.time_matrix[current_node][j]
                    arrival_time = current_time + travel_time + 10 # +10 min servicio
                    deadline = self.points.iloc[j]['deadline_minutos']
                    
                    # Criterio: Más cercano Y que cumpla horario
                    if dist < min_dist and arrival_time <= deadline:
                        min_dist = dist
                        best_next_node = j
            
            if best_next_node != -1:
                # Nos movemos
                visited[best_next_node] = True
                route_indices.append(best_next_node)
                
                # Actualizamos reloj
                travel = self.time_matrix[current_node][best_next_node]
                current_time += travel + 10
                current_node = best_next_node
                
                # Guardamos ID real
                final_route_ids.append(node_to_real_id[best_next_node])
            else:
                # No encontramos ningún nodo válido (todos llegan tarde o ya visitados)
                # En heurística simple, terminamos la ruta aquí o saltamos
                # Para simplificar, cerramos ruta y devolvemos lo que tengamos
                break
        
        # Vuelta a casa
        final_route_ids.append(real_depot_id)
        
        # Si nos hemos dejado clientes sin visitar, la heurística falla parcialmente,
        # pero devuelve una ruta válida.
        return final_route_ids

    def _reconstruct_route(self, x):
        # (Este método es igual que antes, solo para PuLP)
        if 'id' in self.points.columns:
             real_depot_id = self.points.iloc[0]['id']
        else:
             real_depot_id = 0
        route_ids = [real_depot_id]
        node_to_real_id = self.points['id'].to_dict()
        curr = 0
        while True:
            next_node = None
            for j in self.nodes:
                if curr != j and pulp.value(x[curr][j]) == 1:
                    next_node = j; break
            if next_node is None: break
            if next_node != 0:
                route_ids.append(node_to_real_id[next_node])
                curr = next_node
            else:
                route_ids.append(real_depot_id); break
        return route_ids