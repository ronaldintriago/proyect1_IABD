import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
import sys
import os

# Ajuste de path para importar módulos desde src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.controllers.main_controller import LogisticsController
from src.config.fleet_config import FLEET_CONFIG, SIMULATION_START_DATE
# IMPORTAMOS TU NUEVO RENDERIZADOR
from src.utils.map_renderer import create_interactive_map

# Configuración de página
st.set_page_config(page_title="IA Delivery Dashboard", page_icon="🚛", layout="wide")

def render_metrics(res_clustering):
    metrics = res_clustering.get('metrics', {})
    acc_df = res_clustering.get('accepted_df', [])
    disc_df = res_clustering.get('discarded_df', [])
    
    # Gestión de costes
    user_cost = metrics.get('cost', 0)
    if user_cost == 0: user_cost = metrics.get('user_cost', 0)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Coste Total", f"{user_cost:,.2f} €")
    col2.metric("Pedidos Servidos", len(acc_df) if acc_df is not None else 0)
    
    n_disc = len(disc_df) if disc_df is not None else 0
    col3.metric("Descartados", n_disc, delta="-Crítico" if n_disc > 0 else "OK", delta_color="inverse")
    
    # Gestión de ocupación
    details = res_clustering.get('details', [])
    if isinstance(details, dict): details = details.get('user_routes', [])
    
    if details:
        avg = sum([(r['peso']/r['capacidad_max'])*100 for r in details]) / len(details)
        col4.metric("Ocupación Media", f"{avg:.1f}%")
    else:
        col4.metric("Ocupación", "0%")

def main():
    st.title("🚛 Optimización Logística")
    st.caption(f"Fecha Simulación: {SIMULATION_START_DATE}")

    # Lógica de Inicialización
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
            
        if st.button("✨ Ver Solución Ideal"):
            st.cache_data.clear()
            del st.session_state['app_state']
            st.rerun()

    # --- UI PRINCIPAL ---
    render_metrics(state.get('clustering', {}))
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("Mapa de Rutas")
        if state.get('rutas'):
            # AQUÍ LLAMAMOS AL NUEVO MÓDULO LIMPIO
            mapa = create_interactive_map(state['rutas'])
            st_folium(mapa, width=None, height=500, returned_objects=[])
        else:
            st.info("Sin rutas activas")

    with c2:
        st.subheader("Detalle Rutas")
        raw_details = state.get('clustering', {}).get('details', [])
        
        if isinstance(raw_details, dict):
            raw_details = raw_details.get('user_routes', [])
            
        if raw_details:
            df = pd.DataFrame(raw_details)
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