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
from src.data.feature import FeatureEngineer
import logging

logger = logging.getLogger(__name__)

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
    with st.spinner("Cargando dataset..."):
        # Cargar y limpiar tablas crudas
        clientes, destinos, lineas, pedidos, productos, provincias = DataLoader.load_data()

        # Construir diccionario para FeatureEngineer
        dataframes = {
            'clientes': clientes,
            'destinos': destinos,
            'lineas_pedido': lineas,
            'pedidos': pedidos,
            'productos': productos,
            'provincias': provincias
        }

        # Generar dataset maestro de features
        try:
            df_maestro = FeatureEngineer.generar_dataset_maestro(dataframes)
        except Exception as e:
            st.error(f"Error generando dataset maestro: {e}")
            logger.exception("Error en FeatureEngineer.generar_dataset_maestro")
            return

        # Mostrar y también imprimir en consola (terminal)
        st.success("✅ Dataset maestro de features cargado")
        st.subheader("Dataset Maestro (Features)")
        st.dataframe(df_maestro)
        # Imprimir un resumen en la consola donde corre Streamlit
        logger.info("Dataset maestro shape: %s", df_maestro.shape)
        print(df_maestro.head().to_string())




if __name__ == "__main__":
    streamlit_interface()