import pulp
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt

class RouteSolver:
    def __init__(self, df_pedidos, vehicle_speed_kmh=50, max_hours=8):
        """
        df_pedidos: DataFrame con los pedidos de un solo vehículo.
                    Se adapta automáticamente a los nombres de columna del proyecto.
        """
        # 1. Normalización de Nombres de Columnas (Adaptador CSV -> Routing)
        self.points = df_pedidos.copy()
        
        # Diccionario: {NombreEnTuCSV : NombreInternoRouting}
        column_mapping = {
            'PedidoID': 'id',
            'Latitud': 'lat',
            'Longitud': 'lon',
            'vehiculo_nombre': 'nombre',
            'Fecha_Limite_Entrega': 'deadline_date'
        }
        self.points.rename(columns=column_mapping, inplace=True)

        # 2. Gestión de Deadlines (Fecha -> Minutos)
        self.max_minutes = max_hours * 60
        
        # Si no hay columna de minutos, asumimos que tienen todo el turno (480 min)
        if 'deadline_minutos' not in self.points.columns:
            self.points['deadline_minutos'] = self.max_minutes

        # Asegurar IDs y Nombres para reportes
        if 'id' not in self.points.columns:
             self.points['id'] = self.points.index 
        if 'nombre' not in self.points.columns:
            self.points['nombre'] = "Cliente_" + self.points['id'].astype(str)

        # 3. Configuración Física
        self.n_points = len(self.points)
        self.nodes = range(self.n_points)
        self.speed_km_min = vehicle_speed_kmh / 60.0  # Km por minuto
        
        # 4. Pre-calcular matrices
        if self.n_points > 0:
            self.dist_matrix, self.time_matrix = self._calculate_matrices()
        else:
            self.dist_matrix, self.time_matrix = [], []

    def _haversine(self, lat1, lon1, lat2, lon2):
        """Calcula distancia en Km entre dos coordenadas"""
        R = 6371  # Radio tierra km
        try:
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            return R * c
        except ValueError:
            return 0 

    def _calculate_matrices(self):
        """Genera matriz NxN de distancias y tiempos"""
        dist = np.zeros((self.n_points, self.n_points))
        time = np.zeros((self.n_points, self.n_points))
        
        coords = self.points[['lat', 'lon']].values
        
        for i in range(self.n_points):
            for j in range(self.n_points):
                if i != j:
                    d = self._haversine(coords[i][0], coords[i][1], 
                                      coords[j][0], coords[j][1])
                    dist[i][j] = d
                    # Tiempo = Distancia / Velocidad
                    if self.speed_km_min > 0:
                        time[i][j] = d / self.speed_km_min
                    else:
                        time[i][j] = 0
        return dist, time

    def solve(self):
        # Safety Check: Si solo hay 1 punto (Depósito) o ninguno, no hay ruta
        if self.n_points <= 1:
            return []

        # 1. Definir Problema
        prob = pulp.LpProblem("VRP_Routing", pulp.LpMinimize)

        # 2. Variables
        x = pulp.LpVariable.dicts("x", (self.nodes, self.nodes), cat='Binary')
        t = pulp.LpVariable.dicts("t", self.nodes, lowBound=0, upBound=self.max_minutes)
        
        # Fijar inicio en t=0
        prob += t[0] == 0

        # 3. Función Objetivo: Minimizar Distancia
        prob += pulp.lpSum([self.dist_matrix[i][j] * x[i][j] 
                            for i in self.nodes for j in self.nodes if i != j])

        # 4. Restricciones
        
        # 4.1. Visitar cada cliente exactamente una vez
        for i in range(1, self.n_points): 
            prob += pulp.lpSum([x[j][i] for j in self.nodes if i != j]) == 1
            prob += pulp.lpSum([x[i][j] for j in self.nodes if i != j]) == 1

        # 4.2. Salir y volver al Depósito (0)
        prob += pulp.lpSum([x[0][j] for j in range(1, self.n_points)]) == 1
        prob += pulp.lpSum([x[i][0] for i in range(1, self.n_points)]) == 1

        # 4.3. Continuidad temporal (MTZ)
        M = 10000 
        for i in self.nodes:
            for j in range(1, self.n_points):
                if i != j:
                    travel_t = self.time_matrix[i][j]
                    service_t = 10 # 10 min descarga fija por cliente
                    prob += t[j] >= t[i] + service_t + travel_t - M*(1-x[i][j])

        # 4.4. Ventanas de Tiempo (Deadlines)
        for i in range(1, self.n_points):
            deadline = self.points.iloc[i]['deadline_minutos']
            prob += t[i] <= deadline

        # 5. Resolver (Con Límite de Tiempo para velocidad)
        # TimeLimit=10 segundos por ruta. Si no encuentra la óptima perfecta, devuelve la mejor hallada.
        prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=10))

        # 6. Output
        status = pulp.LpStatus[prob.status]
        
        if status == 'Optimal' or status == 'Feasible': # Feasible sirve si cortamos por tiempo
            return self._reconstruct_route(x, t)
        else:
            return None

    def _reconstruct_route(self, x, t):
        # Intentamos recuperar el ID real del depósito si existe
        if 'id' in self.points.columns:
             # Asumiendo que el depósito es la fila 0
             real_depot_id = self.points.iloc[0]['id']
        else:
             real_depot_id = 0
             
        route_ids = [real_depot_id]
        
        # Mapeo inverso: Índice nodo -> ID Real Pedido
        node_to_real_id = self.points['id'].to_dict()

        curr = 0
        while True:
            next_node = None
            for j in self.nodes:
                if curr != j and pulp.value(x[curr][j]) == 1:
                    next_node = j
                    break
            
            if next_node is None: break
            
            if next_node != 0:
                real_id = node_to_real_id[next_node]
                route_ids.append(real_id)
                curr = next_node
            else:
                # Vuelta al depósito
                route_ids.append(real_depot_id)
                break
                
        return route_ids

# --- BLOQUE DE TEST RÁPIDO ---
if __name__ == "__main__":
    try:
        df = pd.read_csv("src/data/processed/dataset_clustered.csv")
        if 'cluster_id' in df.columns:
            cluster_id = df['cluster_id'].unique()[0]
            df_test = df[df['cluster_id'] == cluster_id].copy()
            
            # Crear Depósito Ficticio (necesario para el algoritmo)
            deposito = pd.DataFrame([{
                'PedidoID': 0, 'Latitud': 41.5381, 'Longitud': 2.4447, 
                'vehiculo_nombre': 'CENTRAL', 'Fecha_Limite_Entrega': '2099-01-01'
            }])
            df_input = pd.concat([deposito, df_test], ignore_index=True)

            print(f"🔄 Probando Routing con Cluster {cluster_id}...")
            solver = RouteSolver(df_input, vehicle_speed_kmh=60)
            ruta = solver.solve()
            print(f"Resultado: {ruta}")
    except Exception as e:
        print(f"Test Error: {e}")