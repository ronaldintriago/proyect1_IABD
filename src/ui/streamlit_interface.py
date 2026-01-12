import streamlit as st
import time
import sys
import os
import pandas as pd
from streamlit_folium import st_folium
import plotly.express as px

# Ajuste de path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.controllers.main_controller import LogisticsController
from src.config.fleet_config import FLEET_CONFIG, SIMULATION_START_DATE
from src.utils.map_renderer import create_interactive_map
from src.utils.plot_renderer import AuditPlotter

st.set_page_config(page_title="IA Delivery Dashboard", page_icon="🚛", layout="wide")

# ==============================================================================
# PANTALLAS
# ==============================================================================

def mostrar_pantalla_inicio():
    st.markdown("<h1 style='text-align: center;'>🚛 IA Delivery System</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: gray;'>Configuración de Datos de Entrada</h3>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("📡 **Conexión Empresarial**")
        st.write("Conectar directamente al servidor SQL Server configurado.")
        if st.button("🔌 Conectar a BBDD", use_container_width=True, type="primary"):
            st.session_state['modo_carga'] = 'sql'
            st.session_state['archivos_subidos'] = None
            st.session_state['page'] = 'loading'
            st.rerun()

    with col2:
        st.warning("📂 **Carga Manual (Testing)**")
        st.write("Sube tus propios CSVs para simular nuevos escenarios.")
        
        with st.expander("Subir Archivos CSV", expanded=True):
            uploaded_files = {}
            required = ['Pedidos', 'LineasPedido', 'Productos', 'Clientes', 'Destinos']
            all_present = True
            
            for name in required:
                f = st.file_uploader(f"{name}.csv", type=['csv'], key=name)
                if f: uploaded_files[name] = f
                else: all_present = False
            
            # --- CAMBIO AQUÍ: Ahora pedimos Provincias (Nombres) ---
            f_prov = st.file_uploader("Provincias.csv", type=['csv'], key='prov')
            if f_prov: uploaded_files['Provincias'] = f_prov
            
            if st.button("🚀 Procesar Archivos", disabled=not all_present, use_container_width=True):
                st.session_state['modo_carga'] = 'manual_upload'
                st.session_state['archivos_subidos'] = uploaded_files
                st.session_state['page'] = 'loading'
                st.rerun()

def mostrar_pantalla_carga():
    st.empty()
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>⚙️ Procesando Datos...</h2>", unsafe_allow_html=True)
    bar = st.progress(0); status = st.empty()
    
    status.text("Analizando archivos..."); time.sleep(0.5); bar.progress(10)
    
    try:
        res = LogisticsController.inicializar_sistema(
            st.session_state.get('modo_carga'),
            st.session_state.get('archivos_subidos')
        )
        
        if res['status'] == 'error':
            st.error(res['msg'])
            if st.button("Volver"): st.session_state['page'] = 'inicio'; st.rerun()
            st.stop()
            
        bar.progress(100); status.text("¡Completado!")
        st.session_state['app_state'] = res
        st.session_state['fleet_config_ui'] = res['fleet_used']
        st.session_state['page'] = 'dashboard'
        st.rerun()
        
    except Exception as e:
        st.error(f"Error crítico: {e}")
        st.stop()

def mostrar_dashboard():
    # HEADER
    c1, c2 = st.columns([1, 10])
    c1.title("🚛")
    c2.title("Panel de Control Logístico")
    c2.caption(f"📅 Fecha: {SIMULATION_START_DATE} | 🌐 Modo: {st.session_state.get('modo_carga', 'UNK').upper()}")

    state = st.session_state['app_state']
    
    # SIDEBAR
    with st.sidebar:
        st.header("⚙️ Flota")
        if st.button("🏠 Reiniciar", use_container_width=True):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.session_state['page'] = 'inicio'; st.rerun()
        st.divider()
        
        current = st.session_state.get('fleet_config_ui', {})
        new_input = {}
        for vid, specs in FLEET_CONFIG.items():
            new_input[vid] = st.number_input(f"{specs['nombre']}", value=int(current.get(vid, 0)), min_value=0)
            
        if st.button("🔄 Recalcular", type="primary", use_container_width=True):
            res = LogisticsController.recalcular_con_flota_manual(new_input)
            st.session_state['app_state'] = res
            st.session_state['fleet_config_ui'] = new_input
            st.rerun()

    render_metrics(state.get('clustering', {}))
    
    tab1, tab2, tab3 = st.tabs(["🗺️ Mapa", "📋 Datos", "🔎 Auditoría"])

    with tab1:
        if state.get('rutas'):
            mapa = create_interactive_map(state['rutas'])
            st_folium(mapa, width=None, height=600, returned_objects=[])
        else: st.warning("Sin rutas.")

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Cargas")
            rd = state.get('clustering', {}).get('details', [])
            if isinstance(rd, dict): rd = rd.get('user_routes', [])
            if rd: st.dataframe(pd.DataFrame(rd)[['vehiculo', 'peso', 'coste']], use_container_width=True, hide_index=True)
        with c2:
            st.subheader("Descartes")
            di = state.get('clustering', {}).get('discarded_df')
            if di is not None: st.dataframe(di[['PedidoID', 'nombre_completo']], use_container_width=True, hide_index=True)

    with tab3:
        st.header("🧠 Auditoría")
        rutas = state.get('rutas', [])
        if rutas:
            st.subheader("Zonas (Clustering)")
            fig_c = AuditPlotter.plot_clustering_zones(rutas)
            if fig_c: st.plotly_chart(fig_c, use_container_width=True)
            st.divider()
            st.subheader("Animación (Routing)")
            fig_r = AuditPlotter.plot_routing_animation(rutas)
            if fig_r: st.plotly_chart(fig_r, use_container_width=True)
        else: st.info("Calcula rutas primero.")

def render_metrics(res):
    mets = res.get('metrics', {})
    acc = res.get('accepted_df', [])
    c = mets.get('cost', mets.get('user_cost', 0))
    k1, k2, k3 = st.columns(3)
    k1.metric("Coste", f"{c:,.2f} €")
    k2.metric("Pedidos", len(acc) if acc is not None else 0)
    k3.metric("Eficiencia", "Alta" if c < 2500 else "Media")

def main():
    if 'page' not in st.session_state: st.session_state['page'] = 'inicio'
    if st.session_state['page'] == 'inicio': mostrar_pantalla_inicio()
    elif st.session_state['page'] == 'loading': mostrar_pantalla_carga()
    elif st.session_state['page'] == 'dashboard': mostrar_dashboard()

if __name__ == "__main__":
    main()