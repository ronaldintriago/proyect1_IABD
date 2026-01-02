import pulp
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt

class RouteSolver:
    def __init__(self, df_pedidos, vehicle_speed_kmh=50, max_hours=8):
        """
        df_pedidos: DataFrame con columnas [id, lat, lon, deadline_minutos]
                    (La fila 0 debe ser el DEPÓSITO)
        """
        self.points = df_pedidos
        self.n_points = len(df_pedidos)
        self.nodes = range(self.n_points)
        self.speed_km_min = vehicle_speed_kmh / 60.0  # Km por minuto
        self.max_minutes = max_hours * 60
        
        # Pre-calcular matrices
        self.dist_matrix, self.time_matrix = self._calculate_matrices()

    def _haversine(self, lat1, lon1, lat2, lon2):
        """Calcula distancia en Km entre dos coordenadas"""
        R = 6371  # Radio tierra km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c

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
                    time[i][j] = d / self.speed_km_min
        return dist, time

    def solve(self):
        # --- 0. SAFETY CHECK: Validación de Capacidad ---
        # Sumamos la columna 'cantidad' de todos los pedidos (menos el depósito)
        total_carga = self.points['cantidad'].sum()
        
        # Necesitas tener self.vehicle_capacity_kg guardado en el __init__
        if total_carga > self.vehicle_capacity_kg:
            print(f"❌ ERROR CRÍTICO: El clúster excede la capacidad.")
            print(f"   Carga: {total_carga} Kg > Máx: {self.vehicle_capacity_kg} Kg")
            return None # Rechazamos el grupo sin gastar tiempo de cálculo
        # -----------------------------------------------
        print(f"🔄 Calculando ruta para {self.n_points - 1} pedidos...")
        
        # 1. Definir Problema
        prob = pulp.LpProblem("VRP_Routing_Test", pulp.LpMinimize)

        # 2. Variables
        # x[i][j] = 1 si viaja de i a j
        x = pulp.LpVariable.dicts("x", (self.nodes, self.nodes), cat='Binary')
        # t[i] = tiempo de llegada al nodo i
        t = pulp.LpVariable.dicts("t", self.nodes, lowBound=0, upBound=self.max_minutes)
        # Fijar el tiempo de inicio en el depósito a 0
        prob += t[0] == 0

        # 3. Función Objetivo: Minimizar Distancia Total
        prob += pulp.lpSum([self.dist_matrix[i][j] * x[i][j] for i in self.nodes for j in self.nodes if i != j])

        # 4. Restricciones
        
        # 4.1. Visitar cada cliente exactamente una vez (entrar y salir)
        for i in range(1, self.n_points): 
            prob += pulp.lpSum([x[j][i] for j in self.nodes if i != j]) == 1
            prob += pulp.lpSum([x[i][j] for j in self.nodes if i != j]) == 1

        # 4.2. Salir y volver al Depósito (0)
        prob += pulp.lpSum([x[0][j] for j in range(1, self.n_points)]) == 1
        prob += pulp.lpSum([x[i][0] for i in range(1, self.n_points)]) == 1

        # 4.3. Continuidad temporal y Eliminación de Subtours (MTZ constraint)
        M = 10000 
        for i in self.nodes:
            for j in range(1, self.n_points): # j=1..N (clientes)
                if i != j:
                    travel_t = self.time_matrix[i][j]
                    service_t = 10 # Tiempo fijo descarga (minutos)
                    
                    # Si voy de i -> j, entonces t[j] >= t[i] + viaje + servicio
                    prob += t[j] >= t[i] + service_t + travel_t - M*(1-x[i][j])

        # 4.4. Ventanas de Tiempo (Caducidad)
        for i in range(1, self.n_points):
            deadline = self.points.iloc[i]['deadline_minutos']
            prob += t[i] <= deadline

        # 5. Resolver (usando solver gratuito CBC incluido en PuLP)
        # Ocultamos el log del solver con msg=False
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        # 6. Mostrar Resultados
        status = pulp.LpStatus[prob.status]
        print(f"✅ Estado de la Solución: {status}")
        
        if status == 'Optimal':
            return self._reconstruct_route(x, t)
        else:
            print("❌ No se encontró solución válida (probablemente por tiempos).")
            return None

    def _reconstruct_route(self, x, t):
        route_ids = [0]
        curr = 0
        total_dist = 0
        print("\n--- 🚛 RUTA ÓPTIMA ---")
        
        while True:
            # Buscar a dónde vamos desde 'curr'
            next_node = None
            for j in self.nodes:
                if curr != j and pulp.value(x[curr][j]) == 1:
                    next_node = j
                    break
            
            if next_node is None: break
            
            # Datos para imprimir
            arrival_time = pulp.value(t[next_node]) if next_node != 0 else 0
            dist_tramo = self.dist_matrix[curr][next_node]
            total_dist += dist_tramo
            name = self.points.iloc[next_node]['nombre']
            
            if next_node != 0:
                deadline = self.points.iloc[next_node]['deadline_minutos']
                print(f" -> {name} (Llegada: min {arrival_time:.1f} / Deadline: {deadline}) [Ok]")
                route_ids.append(next_node)
                curr = next_node
            else:
                print(f" -> 🏁 VUELTA A CENTRAL (Distancia total: {total_dist:.2f} km)")
                route_ids.append(0)
                break
                
        return route_ids

# --- BLOQUE DE EJECUCIÓN  ---
if __name__ == "__main__":
    try:
        # 1. Carga robusta: detecta automáticamente si es ',' o ';'
        df = pd.read_csv("test_clustering.csv", sep=None, engine='python')
        
        # 2. Limpieza de nombres de columna (quita espacios extra si los hay)
        df.columns = df.columns.str.strip()

        # 3. Verificación de seguridad
        required_cols = {'id', 'nombre', 'deadline_minutos', 'lat', 'lon'}
        if not required_cols.issubset(df.columns):
            print(f"❌ Error de Columnas. Se esperaban: {required_cols}")
            print(f"   Se encontraron: {df.columns.tolist()}")
            # Intento de arreglo rápido si los nombres difieren por mayúsculas
            df.columns = df.columns.str.lower()
        
        print("📂 Datos cargados correctamente:")
        print(df[['id', 'nombre', 'deadline_minutos']].head())
        print("-" * 30)

        # Inicializar y Resolver
        solver = RouteSolver(df, vehicle_speed_kmh=60, max_hours=8)
        ruta = solver.solve()
        
    except FileNotFoundError:
        print("⚠️ Error: No encuentro 'test_pedidos.csv'. Asegúrate de que está en la misma carpeta.")
    except Exception as e:
        print(f"⚠️ Error inesperado: {e}")