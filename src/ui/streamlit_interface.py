import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.controllers.main_controller import LogisticsController
from src.config.fleet_config import FLEET_CONFIG, SIMULATION_START_DATE

# Configuración de página
st.set_page_config(page_title="IA Delivery Dashboard", page_icon="🚛", layout="wide")

# Constantes visuales
HUB_COORDS = [41.5381, 2.4447]
COLORS = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkpurple', 'black']

# ==============================================================================
# 1. SERVICIO DE TRAZADO (OSRM)
# ==============================================================================
@st.cache_data(show_spinner=False)
def get_full_route_geometry(waypoints):
    if not waypoints or len(waypoints) < 2: return waypoints
    try:
        coords = ";".join([f"{p[1]:.6f},{p[0]:.6f}" for p in waypoints])
        url = f"http://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
        r = requests.get(url, timeout=2.0)
        if r.status_code == 200:
            data = r.json()
            if 'routes' in data and len(data['routes']) > 0:
                geometry = data['routes'][0]['geometry']['coordinates']
                return [[p[1], p[0]] for p in geometry]
    except: pass
    return waypoints

# ==============================================================================
# 2. FUNCIONES DE MAPA
# ==============================================================================
def create_interactive_map(rutas_data):
    m = folium.Map(location=[40.4168, -3.7038], zoom_start=6, tiles="CartoDB positron")
    
    folium.Marker(HUB_COORDS, popup="HUB CENTRAL", icon=folium.Icon(color="black", icon="warehouse", prefix="fa")).add_to(m)

    if not rutas_data: return m

    for i, ruta_info in enumerate(rutas_data):
        color = COLORS[i % len(COLORS)]
        raw_points = []
        detalles = []

        # Normalización de datos de entrada
        orden_paradas = ruta_info.get('ruta', [])
        if isinstance(orden_paradas, pd.DataFrame):
            raw_points = orden_paradas[['Latitud', 'Longitud']].values.tolist()
            detalles = orden_paradas.to_dict('records')
        elif isinstance(orden_paradas, list):
            raw_points = [[p.get('Latitud', p.get('lat')), p.get('Longitud', p.get('lon'))] for p in orden_paradas]
            detalles = orden_paradas

        # Trazado
        ruta_completa = [HUB_COORDS] + raw_points + [HUB_COORDS]
        geometry = get_full_route_geometry(ruta_completa)
        
        folium.PolyLine(locations=geometry, color=color, weight=4, opacity=0.7, tooltip=ruta_info.get('vehiculo')).add_to(m)

        for idx, (coord, det) in enumerate(zip(raw_points, detalles)):
            label = f"P{idx+1}: {det.get('nombre_completo', 'Cliente')}"
            folium.CircleMarker(
                location=coord, radius=5, color=color, fill=True, fill_color="white", fill_opacity=1,
                popup=label, tooltip=label
            ).add_to(m)
    return m

def render_metrics(res_clustering):
    metrics = res_clustering.get('metrics', {})
    acc_df = res_clustering.get('accepted_df', [])
    disc_df = res_clustering.get('discarded_df', [])
    
    # Costes
    user_cost = metrics.get('cost', 0) # A veces viene como 'cost' o 'user_cost' dependiendo del runner
    if user_cost == 0: user_cost = metrics.get('user_cost', 0)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Coste Total", f"{user_cost:,.2f} €")
    col2.metric("Pedidos Servidos", len(acc_df) if acc_df is not None else 0)
    
    n_disc = len(disc_df) if disc_df is not None else 0
    col3.metric("Descartados", n_disc, delta="-Crítico" if n_disc > 0 else "OK", delta_color="inverse")
    
    # Ocupación
    details = res_clustering.get('details', [])
    # CORRECCIÓN ERROR TYPE: Aseguramos que sea lista
    if isinstance(details, dict): details = details.get('user_routes', [])
    
    if details:
        avg = sum([(r['peso']/r['capacidad_max'])*100 for r in details]) / len(details)
        col4.metric("Ocupación Media", f"{avg:.1f}%")
    else:
        col4.metric("Ocupación", "0%")

# ==============================================================================
# 3. MAIN APP
# ==============================================================================
def main():
    st.title("🚛 Optimización Logística")
    st.caption(f"Fecha Simulación: {SIMULATION_START_DATE}")

    if 'app_state' not in st.session_state:
        with st.spinner("Calculando solución óptima..."):
            res = LogisticsController.generar_arranque_automatico()
            if res.get("status") == "error":
                st.error(res.get('msg')); st.stop()
            st.session_state['app_state'] = res
            st.session_state['fleet_config_ui'] = res['clustering']['fleet_used']

    state = st.session_state['app_state']
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Flota")
        
        # Botón para borrar caché si los precios salen a 0
        if st.button("🧹 Borrar Caché y Recargar"):
            st.cache_data.clear()
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
            
        st.divider()
        
        current = st.session_state.get('fleet_config_ui', {})
        new_input = {}
        for vid, specs in FLEET_CONFIG.items():
            new_input[vid] = st.number_input(specs['nombre'], value=int(current.get(vid, 0)), min_value=0)
            
        if st.button("🔄 Recalcular Manual", type="primary"):
            st.session_state['app_state'] = LogisticsController.recalcular_con_flota_manual(new_input)
            st.session_state['fleet_config_ui'] = new_input
            st.rerun()

    # --- UI ---
    render_metrics(state.get('clustering', {}))
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("Mapa de Rutas")
        if state.get('rutas'):
            mapa = create_interactive_map(state['rutas'])
            st_folium(mapa, width=None, height=500, returned_objects=[])
        else:
            st.info("Sin rutas activas")

    with c2:
        st.subheader("Detalle Rutas")
        # --- CORRECCIÓN ERROR TYPE ---
        # Accedemos directamente a 'details' como lista
        raw_details = state.get('clustering', {}).get('details', [])
        
        # Si por alguna razón viniera como dict antiguo, lo extraemos
        if isinstance(raw_details, dict):
            raw_details = raw_details.get('user_routes', [])
            
        if raw_details:
            df = pd.DataFrame(raw_details)
            # CORRECCIÓN WARNING: Usamos use_container_width=True (es lo estándar hoy)
            # Si te sigue dando error, simplemente quita el argumento.
            st.dataframe(
                df[['vehiculo', 'peso', 'paradas', 'coste']].rename(columns={'vehiculo':'Vehículo', 'coste':'€'}),
                hide_index=True,
                use_container_width=True 
            )
        else:
            st.caption("No hay datos de rutas.")
            
        disc = state.get('clustering', {}).get('discarded_df')
        if disc is not None and not disc.empty:
            st.error(f"{len(disc)} Pedidos Perdidos")
            st.dataframe(disc[['PedidoID', 'nombre_completo']], hide_index=True)

if __name__ == "__main__":
    main()