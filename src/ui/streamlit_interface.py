import streamlit as st
import pandas as pd
import os
from streamlit_folium import st_folium

# Importamos los controladores del proyecto
from src.controllers.main_controller import LogisticsController
from src.utils.map_renderer import render_routes_map

# ==============================================================================
# 1. FUNCIÓN DE CACHÉ PARA EL MAPA (IMPORTANTE: EVITA EL BUCLE INFINITO)
# ==============================================================================
@st.cache_resource
def generar_mapa_cacheado(rutas, df_maestro_dict):
    """
    Genera el objeto mapa de Folium y lo guarda en memoria (caché).
    Si los datos no cambian, no vuelve a ejecutar la lógica pesada de OSRM.
    """
    return render_routes_map(rutas, df_maestro_dict)

# ==============================================================================
# 2. INTERFAZ PRINCIPAL
# ==============================================================================
def streamlit_interface():
    st.set_page_config(page_title="IA Delivery", layout="wide", page_icon="🚛")
    st.title("🚛 IA Delivery - Dashboard Logístico")
    
    # ---------------------------------------------------------
    # A. CARGA DE DATOS "NUCLEAR" (PARA QUE NO FALLEN LAS COORDENADAS)
    # ---------------------------------------------------------
    # Intentamos cargar siempre el fichero procesado que usa el algoritmo
    path_seguro = "src/data/datasets/processed/dataset_clustered.csv"
    
    # Si no existe, buscamos alternativas (por si se ejecuta desde otra carpeta)
    if not os.path.exists(path_seguro):
        if os.path.exists("dataset_clustered.csv"):
            path_seguro = "dataset_clustered.csv"
    
    if os.path.exists(path_seguro):
        try:
            df_mapa = pd.read_csv(path_seguro)
            
            # Normalización de nombres de columnas (Blindaje)
            rename_dict = {
                'lat': 'Latitud', 'lon': 'Longitud', 'id': 'PedidoID', 
                'latitud': 'Latitud', 'longitud': 'Longitud'
            }
            df_mapa.rename(columns=rename_dict, inplace=True)
            
            # CONVERSIÓN A STRING PARA EVITAR FALLOS DE ID (Número vs Texto)
            if 'PedidoID' in df_mapa.columns:
                df_mapa['PedidoID'] = df_mapa['PedidoID'].astype(str).str.strip()
            
            st.session_state['df_maestro'] = df_mapa
            # st.success(f"✅ Datos de coordenadas cargados correctamente ({len(df_mapa)} registros).")
            
        except Exception as e:
            st.error(f"Error leyendo CSV de coordenadas: {e}")
    else:
        st.warning("⚠️ No se encuentra 'dataset_clustered.csv'. Ejecuta primero el cálculo para generar datos.")

    # ---------------------------------------------------------
    # B. INICIALIZAR ESTADO (MEMORIA)
    # ---------------------------------------------------------
    if 'resultados_manual' not in st.session_state:
        st.session_state['resultados_manual'] = None
    if 'res_ideal' not in st.session_state:
        st.session_state['res_ideal'] = None

    # TABS
    tab_manual, tab_auto = st.tabs(["🎮 Panel Operativo (Diario)", "✨ Estrategia de Flota (Ideal)"])

    # =========================================================
    # PESTAÑA 1: MODO MANUAL
    # =========================================================
    with tab_manual:
        st.sidebar.header("🕹️ Configuración Diaria")
        
        # Inputs de flota
        n_eco = st.sidebar.number_input("Furgonetas Eco (Tipo 1)", 0, 10, 0)
        n_std = st.sidebar.number_input("Furgonetas Std (Tipo 2)", 0, 10, 2)
        n_rig = st.sidebar.number_input("Camiones Rígidos (Tipo 3)", 0, 10, 0)
        n_trl = st.sidebar.number_input("Tráilers (Tipo 4)", 0, 10, 1)
        
        flota_input = {1: n_eco, 2: n_std, 3: n_rig, 4: n_trl}

        # --- BOTÓN DE CÁLCULO ---
        if st.sidebar.button("🚀 Calcular Rutas (Manual)", key="btn_manual"):
            with st.spinner("🤖 La IA está optimizando las rutas..."):
                # Calculamos y guardamos en sesión
                st.session_state['resultados_manual'] = LogisticsController.ejecutar_calculo_diario(flota_input)

        # --- VISUALIZACIÓN DE RESULTADOS ---
        resultado = st.session_state['resultados_manual']
        
        if resultado:
            # 1. KPIs
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Rutas Creadas", len(resultado["rutas"]))
            servidos = resultado["total_pedidos"] - len(resultado["backlog_capacidad"]) - len(resultado["backlog_tiempo"])
            c2.metric("Pedidos Servidos", servidos)
            backlog = len(resultado["backlog_capacidad"]) + len(resultado["backlog_tiempo"])
            backlog_capacidad = len(resultado["backlog_capacidad"])
            backlog_tiempo = len(resultado["backlog_tiempo"])
            c3.metric("Backlog Capacidad", backlog_capacidad, delta_color="inverse")
            c4.metric("Backlog Tiempo", backlog_tiempo, delta_color="inverse")

            st.divider()

            # 2. MAPA INTERACTIVO (CON CACHÉ Y SIN BUCLE)
            st.subheader("🗺️ Mapa de Rutas")
            
            if resultado["rutas"] and 'df_maestro' in st.session_state:
                try:
                    # Llamada a la función con caché
                    mapa_folium = generar_mapa_cacheado(
                        tuple(resultado["rutas"]), # Tuple para que sea hashable si es necesario (opcional)
                        st.session_state['df_maestro']
                    )
                    
                    # IMPORTANTE: returned_objects=[] evita la recarga al mover el mapa
                    st_folium(mapa_folium, width=1200, height=600, returned_objects=[])
                    
                except Exception as e:
                    st.error(f"💥 Error pintando mapa: {e}")
                    # Si falla, limpiamos caché por si acaso
                    st.cache_resource.clear()
            else:
                if not resultado["rutas"]:
                    st.info("El cálculo finalizó pero no se generaron rutas válidas (revisa el Backlog).")
                else:
                    st.error("Faltan los datos de coordenadas (df_maestro).")

            # 3. DETALLES DE TEXTO
            with st.expander("📄 Ver Secuencia de Paradas (Detalle)"):
                for r in resultado["rutas"]:
                    st.markdown(f"**{r['Tipo']} (ID {r['VehiculoID']})** - {r['Carga']} Kg")
                    # Limpiamos formatos raros de numpy
                    ruta_clean = [int(x) if hasattr(x, 'item') else x for x in r['Ruta']]
                    st.code(str(ruta_clean))

    # =========================================================
    # PESTAÑA 2: MODO IDEAL
    # =========================================================
    with tab_auto:
        st.header("🔮 Cálculo de Flota Perfecta")
        st.caption("La IA determinará cuántos vehículos necesitas exactamente para Backlog 0.")
        
        if st.button("✨ Calcular Solución Óptima", key="btn_auto"):
            with st.spinner("🔄 Iterando escenarios (Cluster -> Routing)..."):
                st.session_state['res_ideal'] = LogisticsController.calcular_flota_perfecta()
        
        res_ideal = st.session_state['res_ideal']
        
        if res_ideal:
            st.success(f"¡Solución encontrada en {res_ideal['iteraciones']} iteraciones!")
            
            # Resumen Flota
            st.write("### 🚛 Flota Recomendada")
            cols = st.columns(len(res_ideal['resumen_flota']))
            idx = 0
            for tipo_id, cant in res_ideal['resumen_flota'].items():
                if idx < len(cols):
                    cols[idx].metric(f"Vehículo Tipo {tipo_id}", f"{cant} uds.")
                    idx += 1

            st.divider()
            st.subheader("🗺️ Visualización Estrategia Ideal")

            if 'df_maestro' in st.session_state:
                try:
                    mapa_ideal = generar_mapa_cacheado(
                        tuple(res_ideal['rutas']), 
                        st.session_state['df_maestro']
                    )
                    st_folium(mapa_ideal, width=1200, height=600, returned_objects=[], key="mapa_ideal")
                except Exception as e:
                    st.error(f"Error mapa ideal: {e}")

if __name__ == "__main__":
    streamlit_interface()