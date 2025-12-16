import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import sys
import os

# Ajuste de path para importar módulos desde src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Importamos el Loader (asegúrate de que el archivo en 'data' se llame 'db_loader.py' como en tu captura)
from src.data.db_loader import DataLoader

# Configuración visual de Seaborn
sns.set_theme(style="whitegrid")

def render_analytics_dashboard(df_vista):
    """Genera los 4 gráficos analíticos avanzados basados en el DataFrame filtrado."""
    
    if len(df_vista) == 0:
        st.warning("⚠️ No hay datos para mostrar con los filtros actuales.")
        return

    st.markdown("### 🔬 Analítica Avanzada (Dinámica)")
    
    # 1. Preparar datos numéricos
    numeric_df = df_vista.select_dtypes(include=['int64', 'float64', 'int32', 'float32'])
    
    if numeric_df.empty:
        st.error("No hay suficientes datos numéricos para generar correlaciones.")
        return

    correlation_matrix = numeric_df.corr()

    # 2. Crear figura (2x2)
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    
    # -- A: Heatmap --
    ax1 = axes[0, 0]
    sns.heatmap(correlation_matrix, annot=True, fmt='.2f', cmap="coolwarm", center=0, ax=ax1)
    ax1.set_title('Matriz de Correlación', fontweight='bold')
    
    # -- B: Top Correlaciones --
    ax2 = axes[0, 1]
    corr_pairs = correlation_matrix.unstack()
    corr_pairs = corr_pairs[corr_pairs != 1.0] # Quitar diagonal
    top_corr = corr_pairs.abs().sort_values(ascending=False).drop_duplicates().head(10)
    
    if not top_corr.empty:
        valores_reales = corr_pairs[top_corr.index]
        colors = ['green' if x > 0 else 'red' for x in valores_reales]
        top_corr.plot(kind='barh', ax=ax2, color=colors, alpha=0.7)
        ax2.set_title('Top Correlaciones Significativas', fontweight='bold')
    else:
        ax2.text(0.5, 0.5, "Datos insuficientes para correlaciones", ha='center')

    # -- C: Histograma Distancia --
    ax3 = axes[1, 0]
    if 'Distancia_Km' in df_vista.columns and not df_vista['Distancia_Km'].isnull().all():
        ax3.hist(df_vista['Distancia_Km'].dropna(), bins=20, color='skyblue', edgecolor='black')
        ax3.set_title('Distribución de Distancias', fontweight='bold')
    
    # -- D: Evolución Temporal --
    ax4 = axes[1, 1]
    if 'FechaPedido' in df_vista.columns:
        fechas = pd.to_datetime(df_vista['FechaPedido'])
        orders_by_date = df_vista.groupby(fechas.dt.date).size()
        ax4.plot(orders_by_date.index, orders_by_date.values, marker='o', color='purple')
        ax4.set_title('Pedidos por Fecha', fontweight='bold')
        ax4.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    st.pyplot(fig)


def streamlit_interface():
    st.set_page_config(page_title="Dashboard SQL Server", layout="wide")
    st.title("📊 Dashboard Integrado (SQL + Analytics)")

    # --- 1. CARGA DE DATOS ---
    try:
        @st.cache_data(ttl=600)
        def cargar_datos_cache():
            return DataLoader.get_master_view()

        with st.spinner("Cargando datos desde SQL Server..."):
            df_vista, raw_tables = cargar_datos_cache()
            # Desempaquetamos las tablas crudas para la Pestaña 3
            clientes, destinos, lineas, pedidos, productos, provincias = raw_tables

    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        st.stop()

    # --- 2. FILTROS (SIDEBAR) ---
    st.sidebar.header("🔍 Filtros Globales")
    st.sidebar.caption("Estos filtros afectan a los Gráficos y a la Tabla Maestra.")
    
    # Filtro Provincia
    provincias_disp = df_vista['Nombre_Provincia'].unique()
    filtro_prov = st.sidebar.multiselect("Filtrar por Provincia", options=provincias_disp)
    
    # Filtro Producto
    productos_disp = df_vista['Producto'].unique()
    filtro_prod = st.sidebar.multiselect("Filtrar por Producto", options=productos_disp)

    # Aplicar filtros al DataFrame principal
    df_filtrado = df_vista.copy()
    if filtro_prov:
        df_filtrado = df_filtrado[df_filtrado['Nombre_Provincia'].isin(filtro_prov)]
    if filtro_prod:
        df_filtrado = df_filtrado[df_filtrado['Producto'].isin(filtro_prod)]

    # Métricas rápidas en sidebar
    st.sidebar.divider()
    st.sidebar.metric("Registros Visibles", len(df_filtrado))
    st.sidebar.metric("Total Ventas", f"{df_filtrado['Total_Linea'].sum():,.2f}€")

    # --- 3. PESTAÑAS PRINCIPALES ---
    tab1, tab2, tab3 = st.tabs(["📉 Analítica Avanzada", "📋 Tabla Maestra Detallada", "🔍 Auditoría de Tablas Crudas"])

    with tab1:
        st.info(f"Mostrando análisis para **{len(df_filtrado)}** registros filtrados.")
        # Llamamos a la función de gráficos pasándole el DF FILTRADO
        render_analytics_dashboard(df_filtrado)

    with tab2:
        st.subheader("Listado de Ventas (Filtrado)")
        st.dataframe(df_filtrado, use_container_width=True)

    with tab3:
        st.subheader("Explorador de Tablas Originales")
        st.markdown("Consulta las tablas tal cual vienen de la base de datos (sin unir).")
        
        opcion_tabla = st.selectbox(
            "Selecciona la tabla a visualizar:", 
            ["Clientes", "Pedidos", "LineasPedido", "Productos", "Destinos", "Provincias"]
        )
        
        if opcion_tabla == "Clientes": st.dataframe(clientes)
        elif opcion_tabla == "Pedidos": st.dataframe(pedidos)
        elif opcion_tabla == "LineasPedido": st.dataframe(lineas)
        elif opcion_tabla == "Productos": st.dataframe(productos)
        elif opcion_tabla == "Destinos": st.dataframe(destinos)
        elif opcion_tabla == "Provincias": st.dataframe(provincias)

if __name__ == "__main__":
    streamlit_interface()