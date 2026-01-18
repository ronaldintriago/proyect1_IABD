import folium
import requests
import pandas as pd
import streamlit as st

# Constantes visuales
HUB_COORDS = [41.5381, 2.4447]  # Mataró
COLORS = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkpurple', 'black']

@st.cache_data(show_spinner=False)
def get_full_route_geometry(waypoints):
    """
    Obtiene la geometría completa de la ruta en UNA SOLA llamada a OSRM.
    Esto es mucho más rápido que pedir tramo a tramo.
    """
    if not waypoints or len(waypoints) < 2:
        return waypoints

    try:
        # Construir string de coordenadas "lon,lat;lon,lat..."
        coords = ";".join([f"{p[1]:.6f},{p[0]:.6f}" for p in waypoints])
        
        # OSRM Demo Server
        url = f"http://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
        
        # Timeout corto para no bloquear la app
        r = requests.get(url, timeout=2.0) 
        
        if r.status_code == 200:
            data = r.json()
            if 'routes' in data and len(data['routes']) > 0:
                geometry = data['routes'][0]['geometry']['coordinates']
                # OSRM devuelve [lon, lat], convertimos a [lat, lon]
                return [[p[1], p[0]] for p in geometry]
    except Exception:
        pass

    return waypoints

def create_interactive_map(rutas_data):
    """
    Genera el objeto Mapa de Folium con las rutas y marcadores.
    """
    m = folium.Map(location=[40.4168, -3.7038], zoom_start=6, tiles="CartoDB positron")

    # Marcador HUB
    folium.Marker(
        location=HUB_COORDS,
        popup="<b>HUB CENTRAL (Mataró)</b>",
        tooltip="Origen",
        icon=folium.Icon(color="black", icon="warehouse", prefix="fa")
    ).add_to(m)

    if not rutas_data:
        return m

    for i, ruta_info in enumerate(rutas_data):
        color = COLORS[i % len(COLORS)]
        nombre_vehiculo = ruta_info.get('vehiculo', f'Vehículo {i+1}')
        orden_paradas = ruta_info.get('ruta', [])
        
        # Extracción de datos agnóstica (acepta DF o lista de dicts)
        if isinstance(orden_paradas, pd.DataFrame):
            raw_points = orden_paradas[['Latitud', 'Longitud']].values.tolist()
            detalles_pedidos = orden_paradas.to_dict('records')
        elif isinstance(orden_paradas, list):
            raw_points = [[p.get('Latitud', p.get('lat')), p.get('Longitud', p.get('lon'))] for p in orden_paradas]
            detalles_pedidos = orden_paradas
        else:
            continue

        if not raw_points:
            continue

        # 1. Trazado de Carretera (Llamada optimizada)
        ruta_completa_puntos = [HUB_COORDS] + raw_points + [HUB_COORDS]
        road_geometry = get_full_route_geometry(ruta_completa_puntos)

        folium.PolyLine(
            locations=road_geometry,
            color=color,
            weight=4,
            opacity=0.7,
            tooltip=f"Ruta {i+1}: {nombre_vehiculo}"
        ).add_to(m)

        # 2. Marcadores de Pedidos
        for idx, (coord, detalle) in enumerate(zip(raw_points, detalles_pedidos)):
            pid = detalle.get('PedidoID', detalle.get('id', '?'))
            peso = detalle.get('Peso_Total_Kg', 0)
            nombre = detalle.get('nombre_completo', 'Cliente')
            
            folium.CircleMarker(
                location=coord,
                radius=5,
                color=color,
                fill=True,
                fill_color="white",
                fill_opacity=1,
                popup=folium.Popup(f"<b>P{idx+1}</b><br>{nombre}<br>Pedido: {pid}<br>{peso} Kg", max_width=200),
                tooltip=f"{idx+1}. {nombre}"
            ).add_to(m)

    return m