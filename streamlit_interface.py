import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard SQL Server", layout="wide")

# --- FUNCIONES DE CARGA Y PROCESADO ---

@st.cache_data(ttl=600)
def cargar_datos_sql():
    """Conecta a SQL Server y descarga las tablas."""
    
    # Credenciales
    server = '10.0.40.12' 
    port = '1433'
    database = 'master' 
    username = 'sa'
    password = 'Stucom.2025'

    # String de conexión
    connection_url = (
        f"mssql+pyodbc://{username}:{password}@{server}:{port}/{database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Encrypt=no&TrustServerCertificate=yes"
    )

    try:
        engine = create_engine(connection_url)
        
        # Consultas SQL
        df_clientes = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Clientes", engine)
        df_destinos = pd.read_sql("SELECT DestinoID, nombre_completo, distancia_km, provinciaID FROM BDIADelivery.dbo.Destinos", engine)
        df_lineas = pd.read_sql("SELECT * FROM BDIADelivery.dbo.LineasPedido", engine)
        df_pedidos = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Pedidos", engine)
        df_productos = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Productos", engine)
        df_provincias = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Provincias", engine)

        df_pedidos['FechaPedido'] = pd.to_datetime(df_pedidos['FechaPedido'])

        return df_clientes, df_destinos, df_lineas, df_pedidos, df_productos, df_provincias
    
        clientes, destinos, lineas, pedidos, productos, provincias = cargar_datos()
        st.success("✅ Datos cargados y tablas correlacionadas correctamente.")

    except Exception as e:
        st.error(f"❌ Error conectando a la base de datos: {e}")
        st.stop()

def procesar_datos(clientes, destinos, lineas, pedidos, productos, provincias):
   # Paso 1: Unir Lineas de Pedido con Pedidos
    master_df = pd.merge(lineas, pedidos, on="PedidoID", how="left")

    # Paso 2: Unir con Productos (para saber el nombre y precio)
    master_df = pd.merge(master_df, productos, on="ProductoID", how="left", suffixes=('_linea', '_prod'))

    # Calculamos el total de la línea (Cantidad * Precio Unitario)
    master_df['Total_Linea'] = master_df['Cantidad'] * master_df['PrecioVenta']

    # Paso 3: Unir con Clientes (Renombramos 'nombre' para que no se confunda)
    clientes = clientes.rename(columns={'nombre': 'Nombre_Cliente'})
    master_df = pd.merge(master_df, clientes, on="ClienteID", how="left")

    # Paso 4: Unir con Destinos (Ojo: Pedidos usa 'DestinoEntregaID' y Destinos usa 'DestinoID')
    master_df = pd.merge(master_df, destinos, left_on="DestinoEntregaID", right_on="DestinoID", how="left")

    # Paso 5: Unir con Provincias (para saber la provincia del destino)
    # Nota: Destinos tiene 'provinciaID' y Provincias tiene 'ProvinciaID'
    provincias = provincias.rename(columns={'nombre': 'Nombre_Provincia'})
    master_df = pd.merge(master_df, provincias, left_on="provinciaID", right_on="ProvinciaID", how="left")

    # Limpieza final: Seleccionar y ordenar columnas para que se vea bonito
    columnas_finales = [
        'PedidoID', 'FechaPedido', 'Nombre_Cliente', 'email', 
        'Nombre', 'Cantidad', 'PrecioVenta', 'Total_Linea', # 'Nombre' es el del producto
        'nombre_completo', 'Nombre_Provincia', 'pais' # 'nombre_completo' es el destino
    ]
    # Renombramos la columna 'Nombre' del producto a 'Producto' para mayor claridad
    master_df = master_df.rename(columns={'Nombre': 'Producto', 'nombre_completo': 'Destino', 'distancia_km': 'Distancia_Km'})
    vista_final = master_df[['PedidoID', 'FechaPedido', 'Nombre_Cliente', 'Producto', 'Cantidad', 'Total_Linea', 'Destino', 'Nombre_Provincia', 'Distancia_Km']]
    return vista_final

# --- MAIN (PUNTO DE ENTRADA) ---

def streamlit_interface():
    st.title("📊 Dashboard de Ventas (SQL Server)")

    # 1. Cargar
    with st.spinner("Conectando a SQL Server..."):
        clientes, destinos, lineas, pedidos, productos, provincias = cargar_datos_sql()

    # 2. Procesar
    df_vista = procesar_datos(clientes, destinos, lineas, pedidos, productos, provincias)

    # --- 3. VISUALIZACIÓN ---

    # Crear pestañas para organizar la vista
    tab1, tab2, tab3 = st.tabs(["📋 Tabla Maestra Unificada", "📈 Estadísticas", "🔍 Explorador de Tablas"])

    with tab1:
        st.subheader("Vista completa de la Base de Datos")
        st.markdown("Esta tabla es el resultado de unir tus 6 CSVs.")
        
        # Filtros en la barra lateral
        st.sidebar.header("Filtros")
        filtro_provincia = st.sidebar.multiselect("Filtrar por Provincia", options=df_vista['Nombre_Provincia'].unique())
        filtro_producto = st.sidebar.multiselect("Filtrar por Producto", options=df_vista['Producto'].unique())

        df_filtrado = df_vista.copy()
        if filtro_provincia:
            df_filtrado = df_filtrado[df_filtrado['Nombre_Provincia'].isin(filtro_provincia)]
        if filtro_producto:
            df_filtrado = df_filtrado[df_filtrado['Producto'].isin(filtro_producto)]

        st.dataframe(df_filtrado, use_container_width=True)
        st.caption(f"Mostrando {len(df_filtrado)} registros.")

    with tab2:
        st.subheader("Indicadores Clave (KPIs)")
        
        col1, col2, col3, col4 = st.columns(4)
        total_ventas = df_filtrado['Total_Linea'].sum()
        total_pedidos = df_filtrado['PedidoID'].nunique()
        top_cliente = df_filtrado.groupby('Nombre_Cliente')['Total_Linea'].sum().idxmax()
        
        col1.metric("Ventas Totales", f"{total_ventas:,.2f}€")
        col2.metric("Total Pedidos", total_pedidos)
        col3.metric("Cliente Top", top_cliente)
        col4.metric("Registros Visibles", len(df_filtrado))
        
        st.divider()
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("##### Ventas por Provincia")
            ventas_provincia = df_filtrado.groupby('Nombre_Provincia')['Total_Linea'].sum().reset_index()
            fig_prov = px.bar(ventas_provincia, x='Nombre_Provincia', y='Total_Linea', color='Total_Linea')
            st.plotly_chart(fig_prov, use_container_width=True)
            
        with col_chart2:
            st.markdown("##### Top 10 Productos Más Vendidos")
            top_prod = df_filtrado.groupby('Producto')['Cantidad'].sum().nlargest(10).reset_index()
            fig_prod = px.pie(top_prod, values='Cantidad', names='Producto', hole=0.4)
            st.plotly_chart(fig_prod, use_container_width=True)

    with tab3:
        st.info("Aquí puedes ver tus tablas originales sin procesar para verificar datos.")
        opcion = st.selectbox("Selecciona tabla original:", ["Clientes", "Pedidos", "LineasPedido", "Productos", "Destinos", "Provincias"])
        
        if opcion == "Clientes": st.dataframe(clientes)
        elif opcion == "Pedidos": st.dataframe(pedidos)
        elif opcion == "LineasPedido": st.dataframe(lineas)
        elif opcion == "Productos": st.dataframe(productos)
        elif opcion == "Destinos": st.dataframe(destinos)
        elif opcion == "Provincias": st.dataframe(provincias)

