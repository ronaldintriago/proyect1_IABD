import folium
import requests
import polyline
import time
import random  # <--- NECESARIO PARA EL TRUCO VISUAL
from functools import lru_cache

CENTRAL_COORDS = [41.5381, 2.4447]

def get_color(index):
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'black']
    return colors[index % len(colors)]

@lru_cache(maxsize=2000)
def get_osrm_route_cached(lat1, lon1, lat2, lon2):
    """
    Obtiene la geometría de la carretera real (caché para velocidad).
    """
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=polyline"
    try:
        r = requests.get(url, timeout=1) 
        if r.status_code == 200:
            data = r.json()
            if 'routes' in data and len(data['routes']) > 0:
                return polyline.decode(data['routes'][0]['geometry'])
    except:
        pass
    return None

def render_routes_map(rutas_calculadas, df_maestro):
    print("🗺️ GENERANDO MAPA CON EFECTO RACIMO...")
    
    m = folium.Map(location=CENTRAL_COORDS, zoom_start=10)
    
    # Marcador Central (Sin desplazamiento, este es fijo)
    folium.Marker(
        location=CENTRAL_COORDS,
        popup="🏭 CENTRAL MATARÓ",
        icon=folium.Icon(color='black', icon='home', prefix='fa'),
        z_index_offset=1000
    ).add_to(m)

    # Preparar Datos
    df = df_maestro.copy()
    if 'id' in df.columns: df.rename(columns={'id': 'PedidoID'}, inplace=True)
    if 'lat' in df.columns: df.rename(columns={'lat': 'Latitud'}, inplace=True)
    if 'lon' in df.columns: df.rename(columns={'lon': 'Longitud'}, inplace=True)
    
    df['PedidoID'] = df['PedidoID'].astype(str).str.strip()
    coords_lookup = df.set_index('PedidoID')[['Latitud', 'Longitud']].to_dict('index')
    
    all_points = [CENTRAL_COORDS]
    
    for idx, ruta_info in enumerate(rutas_calculadas):
        vehiculo_id = ruta_info['VehiculoID']
        tipo = ruta_info['Tipo']
        secuencia = ruta_info['Ruta'] 

        # Filtro de seguridad
        if len(secuencia) <= 2: continue

        color = get_color(idx)
        feature_group = folium.FeatureGroup(name=f"{tipo} #{vehiculo_id}")
        
        prev_point = CENTRAL_COORDS
        
        for i, pedido_id in enumerate(secuencia):
            pid_str = str(pedido_id).strip()
            
            if pid_str == "0":
                curr_point = CENTRAL_COORDS
                nombre = "Central"
            elif pid_str in coords_lookup:
                data = coords_lookup[pid_str]
                curr_point = [data['Latitud'], data['Longitud']]
                nombre = f"Cliente {pid_str}"
            else:
                continue

            all_points.append(curr_point)

            # --- TRUCO VISUAL: EL JITTER ---
            # Si NO es la central, aplicamos un micro-desplazamiento aleatorio al MARCADOR.
            # (La línea de la carretera seguirá yendo al punto exacto original).
            if i > 0 and pid_str != "0": 
                
                # Desplazamiento de +/- 0.0003 grados (~30 metros)
                lat_jitter = curr_point[0] + random.uniform(-0.0003, 0.0003)
                lon_jitter = curr_point[1] + random.uniform(-0.0003, 0.0003)
                point_visual = [lat_jitter, lon_jitter]

                folium.Marker(
                    location=point_visual, # Usamos el punto desplazado
                    popup=f"Ruta: {vehiculo_id}<br>ID: {pid_str}",
                    tooltip=f"{i}. {nombre}", # El tooltip te ayuda a ver cuál es cuál
                    icon=folium.Icon(color=color, icon='box', prefix='fa', icon_size=(20,20))
                ).add_to(feature_group)

            # --- LÍNEA DE RUTA ---
            # Usamos los puntos REALES (curr_point) para que la carretera sea correcta
            if i > 0:
                real_road = get_osrm_route_cached(prev_point[0], prev_point[1], curr_point[0], curr_point[1])
                
                if real_road:
                    folium.PolyLine(real_road, color=color, weight=4, opacity=0.8).add_to(feature_group)
                else:
                    folium.PolyLine([prev_point, curr_point], color=color, weight=4, opacity=0.8, dash_array='5, 10').add_to(feature_group)

            prev_point = curr_point

        feature_group.add_to(m)

    if len(all_points) > 1:
        m.fit_bounds(all_points)

    folium.LayerControl().add_to(m)
    return m