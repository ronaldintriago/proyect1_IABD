import streamlit as st
import time
import sys
import os

# Ajuste imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.controllers.main_controller import LogisticsController
from src.config.fleet_config import FLEET_CONFIG, SIMULATION_START_DATE
from src.utils.map_renderer import create_interactive_map
from streamlit_folium import st_folium
import pandas as pd

# Configuración inicial
st.set_page_config(page_title="IA Logistics", page_icon="🚛", layout="wide")

# ==============================================================================
# GESTIÓN DE PANTALLAS
# ==============================================================================

def mostrar_pantalla_inicio():
    """Pantalla 1: Selección de Fuente de Datos"""
    st.markdown("<h1 style='text-align: center;'>🚛 IA Delivery System</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: gray;'>Selecciona el origen de los datos para iniciar la simulación</h3>", unsafe_allow_html=True)
    
    st.write("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Botones grandes
        btn_sql = st.button("🔌 Conectar a Servidor SQL", use_container_width=True, type="primary")
        st.write("") # Espacio
        btn_csv = st.button("📂 Cargar Archivos CSV Locales", use_container_width=True)

    if btn_sql:
        st.session_state['modo_carga'] = 'sql'
        st.session_state['page'] = 'loading'
        st.rerun()
        
    if btn_csv:
        st.session_state['modo_carga'] = 'csv'
        st.session_state['page'] = 'loading'
        st.rerun()

def mostrar_pantalla_carga():
    """Pantalla 2: Loading con barra de progreso"""
    st.empty() # Limpiar pantalla anterior
    
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>🚀 Inicializando Motores de IA...</h2>", unsafe_allow_html=True)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 1. Extracción
    status_text.text("Conectando con fuente de datos...")
    time.sleep(1) # Fake delay para efecto visual chulo
    progress_bar.progress(20)
    
    # 2. Transformación
    status_text.text("Normalizando datos y calculando features...")
    time.sleep(0.5)
    progress_bar.progress(40)
    
    # LLAMADA REAL AL CONTROLADOR
    # Aquí es donde ocurre la magia real
    modo = st.session_state.get('modo_carga', 'csv')
    
    try:
        resultado = LogisticsController.inicializar_sistema(modo)
    except Exception as e:
        st.error(f"Error crítico: {e}")
        st.stop()

    if resultado['status'] == 'error':
        st.error(resultado['msg'])
        if st.button("Volver"):
            st.session_state['page'] = 'inicio'
            st.rerun()
        st.stop()

    # 3. Clustering
    status_text.text("Ejecutando algoritmo K-Means (Clustering)...")
    progress_bar.progress(70)
    
    # 4. Routing
    status_text.text("Optimizando rutas con OSRM y PuLP...")
    progress_bar.progress(90)
    time.sleep(0.5)
    
    # Finalizar
    progress_bar.progress(100)
    status_text.text("¡Sistema listo!")
    time.sleep(0.5)
    
    # Guardar en sesión y saltar al dashboard
    st.session_state['app_state'] = resultado
    st.session_state['fleet_config_ui'] = resultado['fleet_used']
    st.session_state['page'] = 'dashboard'
    st.rerun()

def mostrar_dashboard():
    """Pantalla 3: La interfaz principal que ya tenías"""
    
    # --- HEADER ---
    c_logo, c_title = st.columns([1, 10])
    with c_logo:
        st.write("🚛") # Aquí podrías poner st.image('assets/logo.png')
    with c_title:
        st.title("Panel de Control Logístico")
        st.caption(f"Simulación activa: {SIMULATION_START_DATE} | Modo: {st.session_state.get('modo_carga', 'UNK').upper()}")

    state = st.session_state['app_state']
    
    # --- SIDEBAR (FLOTA) ---
    with st.sidebar:
        st.header("⚙️ Gestión de Flota")
        
        # Botón Reset
        if st.button("🏠 Inicio / Reset", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.session_state['page'] = 'inicio'
            st.rerun()
            
        st.divider()
        
        # Inputs Flota
        current = st.session_state.get('fleet_config_ui', {})
        new_input = {}
        for vid, specs in FLEET_CONFIG.items():
            new_input[vid] = st.number_input(specs['nombre'], value=int(current.get(vid, 0)), min_value=0)
            
        if st.button("🔄 Recalcular", type="primary"):
            with st.spinner("Reajustando rutas..."):
                res = LogisticsController.recalcular_con_flota_manual(new_input)
                st.session_state['app_state'] = res
                st.session_state['fleet_config_ui'] = new_input
                st.rerun()
        
        if st.button("✨ Restaurar Óptimo"):
             # Truco: volver a ejecutar el init automático
             st.session_state['page'] = 'loading' 
             st.rerun()

    # --- MÉTRICAS (Igual que antes) ---
    render_metrics(state.get('clustering', {}))
    
    # --- MAPA Y TABLAS (Igual que antes) ---
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Mapa en Tiempo Real")
        if state.get('rutas'):
            mapa = create_interactive_map(state['rutas'])
            st_folium(mapa, width=None, height=600, returned_objects=[])
        else:
            st.warning("No hay rutas generadas.")
            
    with c2:
        st.subheader("Detalle Operativo")
        # ... (Tu código de tablas existente va aquí) ...
        # (He resumido para brevedad, pega aquí tu bloque de dataframe)
        raw_details = state.get('clustering', {}).get('details', [])
        if isinstance(raw_details, dict): raw_details = raw_details.get('user_routes', [])
        if raw_details:
             df = pd.DataFrame(raw_details)
             st.dataframe(df[['vehiculo', 'peso', 'coste']], use_container_width=True, hide_index=True)


def render_metrics(res_clustering):
    # ... (Tu función de métricas que ya funciona perfecta) ...
    metrics = res_clustering.get('metrics', {})
    acc_df = res_clustering.get('accepted_df', [])
    cost = metrics.get('cost', metrics.get('user_cost', 0))
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Coste Operativo", f"{cost:.2f} €")
    k2.metric("Pedidos Entregados", len(acc_df))
    k3.metric("Eficiencia", "Alta" if cost < 2000 else "Mejorable")

# ==============================================================================
# MAIN ROUTER
# ==============================================================================

def main():
    # Inicializar estado de página
    if 'page' not in st.session_state:
        st.session_state['page'] = 'inicio'

    # Router simple
    if st.session_state['page'] == 'inicio':
        mostrar_pantalla_inicio()
    elif st.session_state['page'] == 'loading':
        mostrar_pantalla_carga()
    elif st.session_state['page'] == 'dashboard':
        mostrar_dashboard()

if __name__ == "__main__":
    main()