import streamlit as st
import time
import sys
import os
import pandas as pd
from streamlit_folium import st_folium

# Ajuste de path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.controllers.main_controller import LogisticsController
from src.config.fleet_config import FLEET_CONFIG, SIMULATION_START_DATE
from src.utils.map_renderer import create_interactive_map
# NUEVO IMPORT
from src.utils.plot_renderer import AuditPlotter

st.set_page_config(page_title="IA Delivery Dashboard", page_icon="🚛", layout="wide")

# ==============================================================================
# COMPONENTES UI (Helpers visuales)
# ==============================================================================

def render_metrics(res_clustering):
    """Componente reutilizable de métricas KPI"""
    metrics = res_clustering.get('metrics', {})
    acc_df = res_clustering.get('accepted_df', [])
    cost = metrics.get('cost', metrics.get('user_cost', 0))
    
    # Contenedor estilizado
    with st.container():
        k1, k2, k3 = st.columns(3)
        k1.metric("💰 Coste Operativo", f"{cost:,.2f} €")
        k2.metric("📦 Pedidos Entregados", len(acc_df) if acc_df is not None else 0)
        status = "🟢 Óptima" if cost < 2500 else "🟠 Mejorable"
        k3.metric("📊 Eficiencia Global", status)
    st.divider()

# ==============================================================================
# PANTALLAS
# ==============================================================================

def mostrar_pantalla_inicio():
    st.markdown("<h1 style='text-align: center;'>🚛 IA Delivery System</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Sistema inteligente de optimización logística VRP</p>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("📡 **Entorno Empresarial (SQL Server)**")
        st.write("Conexión directa al Data Warehouse corporativo.")
        if st.button("🔌 Conectar a Base de Datos", use_container_width=True, type="primary"):
            st.session_state['modo_carga'] = 'sql'
            st.session_state['archivos_subidos'] = None
            st.session_state['page'] = 'loading'
            st.rerun()

    with col2:
        st.warning("📂 **Entorno de Simulación (Archivos Locales)**")
        st.write("Carga de datasets manuales para pruebas de estrés.")
        
        with st.expander("Subir Archivos CSV", expanded=True):
            uploaded_files = {}
            required = ['Pedidos', 'LineasPedido', 'Productos', 'Clientes', 'Destinos']
            all_present = True
            
            for name in required:
                f = st.file_uploader(f"{name}.csv", type=['csv'], key=name)
                if f: uploaded_files[name] = f
                else: all_present = False
            
            f_geo = st.file_uploader("Provincias_geo.csv (Opcional)", type=['csv'], key='geo')
            if f_geo: uploaded_files['Provincias_geo'] = f_geo
            
            if st.button("🚀 Iniciar Simulación", disabled=not all_present, use_container_width=True):
                st.session_state['modo_carga'] = 'manual_upload'
                st.session_state['archivos_subidos'] = uploaded_files
                st.session_state['page'] = 'loading'
                st.rerun()

def mostrar_pantalla_carga():
    st.empty()
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>⚙️ Inicializando Motores de IA...</h2>", unsafe_allow_html=True)
    
    bar = st.progress(0); status = st.empty()
    status.text("Conectando con origen de datos..."); time.sleep(0.3); bar.progress(20)
    
    try:
        res = LogisticsController.inicializar_sistema(
            st.session_state.get('modo_carga'),
            st.session_state.get('archivos_subidos')
        )
        
        if res['status'] == 'error':
            st.error(f"❌ {res['msg']}")
            if st.button("Volver al Inicio"): 
                st.session_state['page'] = 'inicio'; st.rerun()
            st.stop()
            
        bar.progress(100); status.text("¡Sistema Listo!")
        time.sleep(0.5)
        
        st.session_state['app_state'] = res
        st.session_state['fleet_config_ui'] = res['fleet_used']
        st.session_state['page'] = 'dashboard'
        st.rerun()
        
    except Exception as e:
        st.error(f"Error crítico no controlado: {e}")
        st.stop()

def mostrar_dashboard():
    # HEADER
    c1, c2 = st.columns([1, 10])
    c1.title("🚛")
    c2.title("Panel de Control Logístico")
    c2.caption(f"📅 Fecha Simulación: {SIMULATION_START_DATE} | 🌐 Modo: {st.session_state.get('modo_carga', 'UNK').upper()}")

    state = st.session_state['app_state']
    
    # SIDEBAR
    with st.sidebar:
        st.header("⚙️ Configuración Flota")
        if st.button("🏠 Reiniciar Sistema", use_container_width=True):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.session_state['page'] = 'inicio'
            st.rerun()
        st.divider()
        
        # Inputs dinámicos
        current = st.session_state.get('fleet_config_ui', {})
        new_input = {}
        for vid, specs in FLEET_CONFIG.items():
            new_input[vid] = st.number_input(
                f"{specs['nombre']} ({specs['capacidad_kg']}kg)", 
                value=int(current.get(vid, 0)), 
                min_value=0
            )
            
        if st.button("🔄 Recalcular Rutas", type="primary", use_container_width=True):
            with st.spinner("Reajustando logística..."):
                res = LogisticsController.recalcular_con_flota_manual(new_input)
                st.session_state['app_state'] = res
                st.session_state['fleet_config_ui'] = new_input
                st.rerun()
        
        if st.button("✨ Restaurar Óptimo (IA)", use_container_width=True):
             st.session_state['page'] = 'loading'; st.rerun()

    # KPI TOP
    render_metrics(state.get('clustering', {}))
    
    # TABS PRINCIPALES
    tab1, tab2, tab3 = st.tabs(["🗺️ Mapa Operativo", "📋 Datos Detallados", "🔎 Auditoría IA"])

    # TAB 1: OPERATIVA DIARIA (Lo que mira el jefe de tráfico)
    with tab1:
        if state.get('rutas'):
            mapa = create_interactive_map(state['rutas'])
            st_folium(mapa, width=None, height=600, returned_objects=[])
        else:
            st.warning("⚠️ No se han podido generar rutas con la configuración actual.")

    # TAB 2: DETALLES (Lo que mira administración)
    with tab2:
        c_left, c_right = st.columns([2, 1])
        with c_left:
            st.subheader("Hoja de Ruta")
            raw_details = state.get('clustering', {}).get('details', [])
            if isinstance(raw_details, dict): raw_details = raw_details.get('user_routes', [])
            
            if raw_details:
                df = pd.DataFrame(raw_details)
                st.dataframe(
                    df[['vehiculo', 'peso', 'coste', 'paradas']].rename(columns={'vehiculo':'Vehículo', 'peso':'Carga (Kg)', 'coste':'Coste (€)'}),
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("Sin datos.")

        with c_right:
            st.subheader("Incidencias / Descartes")
            disc = state.get('clustering', {}).get('discarded_df')
            if disc is not None and not disc.empty:
                st.error(f"{len(disc)} Pedidos sin asignar")
                st.dataframe(disc[['PedidoID', 'nombre_completo']], use_container_width=True, hide_index=True)
            else:
                st.success("✅ 100% Cobertura")

    # TAB 3: AUDITORÍA (Lo que mira el analista de datos)
    with tab3:
        st.header("🧠 Explicabilidad del Modelo")
        rutas = state.get('rutas', [])
        
        if rutas:
            st.subheader("1. Mapa de Calor & Zonas (Clustering)")
            st.caption("Visualización de cómo el algoritmo K-Means ha agrupado los pedidos por proximidad.")
            fig_c = AuditPlotter.plot_clustering_zones(rutas)
            if fig_c: st.plotly_chart(fig_c, use_container_width=True)
            
            st.divider()

            st.subheader("2. Simulación de Ejecución (Routing)")
            st.caption("Reconstrucción paso a paso de la toma de decisiones de ruta.")
            fig_r = AuditPlotter.plot_routing_animation(rutas)
            if fig_r: 
                st.plotly_chart(fig_r, use_container_width=True)
                st.info("ℹ️ Usa el botón ▶️ o el slider inferior para ver la animación temporal.")
            else:
                st.warning("Datos insuficientes para la animación.")
        else:
            st.info("Se requiere ejecutar una simulación primero.")

def main():
    if 'page' not in st.session_state: st.session_state['page'] = 'inicio'
    
    if st.session_state['page'] == 'inicio': mostrar_pantalla_inicio()
    elif st.session_state['page'] == 'loading': mostrar_pantalla_carga()
    elif st.session_state['page'] == 'dashboard': mostrar_dashboard()

if __name__ == "__main__":
    main()