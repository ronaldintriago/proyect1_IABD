import logging
import pandas as pd
from datetime import timedelta

logger = logging.getLogger(__name__)


class FeatureEngineer:
    @staticmethod
    def generar_dataset_maestro(dataframes):
        """Genera el dataset maestro a partir de los DataFrames limpios.

        Esta versión normaliza tipos (especialmente IDs de provincia) para evitar
        errores de merge entre columnas object/int64.
        """
        # 1. Obtener DataFrames limpios
        df_pedidos = dataframes["pedidos"]
        df_lineas = dataframes["lineas_pedido"]
        df_prod = dataframes["productos"]
        df_dest = dataframes["destinos"]
        df_prov = dataframes["provincias"]

        # Normalizaciones y validaciones previas
        # Asegurar FechaPedido es datetime
        if 'FechaPedido' in df_pedidos.columns:
            df_pedidos['FechaPedido'] = pd.to_datetime(df_pedidos['FechaPedido'], errors='coerce')

        # Coercionar IDs de provincia a numéricos para que merge no falle por tipos distintos
        if 'provinciaID' in df_dest.columns:
            df_dest['provinciaID'] = pd.to_numeric(df_dest['provinciaID'], errors='coerce')
        if 'ProvinciaID' in df_prov.columns:
            df_prov['ProvinciaID'] = pd.to_numeric(df_prov['ProvinciaID'], errors='coerce')

        logger.info("ProvinciaID types: destinos=%s, provincias=%s",
                    df_dest['provinciaID'].dtype if 'provinciaID' in df_dest.columns else 'n/a',
                    df_prov['ProvinciaID'].dtype if 'ProvinciaID' in df_prov.columns else 'n/a')

        # Asegurar que columnas numéricas de producto no contengan NaN
        for col in ['TiempoFabricacionMedio', 'Caducidad']:
            if col in df_prod.columns:
                df_prod[col] = pd.to_numeric(df_prod[col], errors='coerce').fillna(0)

        # 2. Enriquecer Líneas con Datos de Producto (Caducidad y Fabricación)
        df_full_lines = pd.merge(
            df_lineas,
            df_prod[['ProductoID', 'TiempoFabricacionMedio', 'Caducidad']],
            on='ProductoID',
            how='left'
        )

        # Unir con Pedidos para tener la fecha de referencia
        df_full_lines = pd.merge(
            df_full_lines,
            df_pedidos[['PedidoID', 'FechaPedido']],
            on='PedidoID',
            how='left'
        )

        # 3. Calcular Fechas Límites por Línea (protegido contra valores nulos)
        def calc_fecha_limite(row):
            fecha = row.get('FechaPedido')
            if pd.isna(fecha):
                return pd.NaT
            tf = row.get('TiempoFabricacionMedio', 0) or 0
            cad = row.get('Caducidad', 0) or 0
            try:
                dias = int(tf + cad)
            except Exception:
                dias = 0
            return fecha + timedelta(days=dias)

        df_full_lines['Fecha_Limite_Item'] = df_full_lines.apply(calc_fecha_limite, axis=1)

        # 4. AGRUPACIÓN (Colapsar líneas en Pedidos Únicos)
        df_maestro = df_full_lines.groupby('PedidoID').agg({
            'Cantidad': 'sum',
            'Fecha_Limite_Item': 'min',
            'FechaPedido': 'first'
        }).reset_index()

        df_maestro.rename(columns={
            'Cantidad': 'Peso_Total_Kg',
            'Fecha_Limite_Item': 'Fecha_Limite_Entrega'
        }, inplace=True)

        # 5. Unir con Destinos y Provincias
        df_maestro = pd.merge(
            df_maestro,
            df_pedidos[['PedidoID', 'DestinoEntregaID']],
            on='PedidoID',
            how='left'
        )

        df_maestro = pd.merge(
            df_maestro,
            df_dest,
            left_on='DestinoEntregaID',
            right_on='DestinoID',
            how='left'
        )

        # Merge con provincias usando claves numéricas ya coercionadas
        df_maestro = pd.merge(
            df_maestro,
            df_prov,
            left_on='provinciaID',
            right_on='ProvinciaID',
            how='left'
        )

        # 6. LIMPIEZA FINAL DE COLUMNAS (verificar que existan)
        cols_necesarias = [
            'PedidoID',
            'Peso_Total_Kg',
            'Fecha_Limite_Entrega',
            'nombre_completo',
            'distancia_km',
            'coordenadas_gps'
        ]

        # Filtrar solo columnas existentes de forma segura
        cols_presentes = [c for c in cols_necesarias if c in df_maestro.columns]
        missing = set(cols_necesarias) - set(cols_presentes)
        if missing:
            logger.warning("Faltan columnas esperadas en df_maestro: %s", missing)

        # Añadir columna 'coordenadas' combinada: preferimos coordenadas_gps si existe,
        # luego Latitud/Longitud de provincias y finalmente None.
        def parse_gps(val):
            if pd.isna(val):
                return None
            try:
                s = str(val).strip().replace('(', '').replace(')', '')
                parts = [p.strip() for p in s.split(',')]
                if len(parts) >= 2:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    return (lat, lon)
            except Exception:
                return None
            return None

        # start with None
        df_maestro['coordenadas'] = None

        # If coordenadas_gps column exists, try to parse
        if 'coordenadas_gps' in df_maestro.columns:
            df_maestro['coordenadas'] = df_maestro['coordenadas_gps'].apply(parse_gps)

        # Where still None, try Latitud/Longitud
        if 'Latitud' in df_maestro.columns and 'Longitud' in df_maestro.columns:
            mask_missing = df_maestro['coordenadas'].isna()
            df_maestro.loc[mask_missing, 'coordenadas'] = df_maestro.loc[mask_missing].apply(
                lambda r: (float(r['Latitud']), float(r['Longitud'])) if (pd.notna(r['Latitud']) and pd.notna(r['Longitud'])) else None,
                axis=1
            )

        filled = df_maestro['coordenadas'].notna().sum()
        logger.info("Coordenadas asignadas en df_maestro: %d/%d", filled, len(df_maestro))

        # Ensure 'coordenadas' is in the returned columns
        if 'coordenadas' not in cols_presentes:
            cols_presentes.append('coordenadas')

        return df_maestro[cols_presentes]