import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCleaner:
    """Clase para limpiar y validar datos de la base de datos de entregas."""

    @staticmethod
    def clean_dataframe(dash_loaded_data: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza el dataframe eliminando espacios en blanco en columnas de texto.

        Parameters
        ----------
        dash_loaded_data : pd.DataFrame
            Los datos a limpiar.

        Returns
        -------
        cleaned_dash_loaded_data : pd.DataFrame
            Los datos limpios.
        """
        cleaned_dash_loaded_data = dash_loaded_data.copy()
        for col in cleaned_dash_loaded_data.select_dtypes(include="object").columns:
            cleaned_dash_loaded_data[col] = (
                cleaned_dash_loaded_data[col].astype(str).str.strip()
            )
        return cleaned_dash_loaded_data

    @staticmethod
    def validate_and_clean_dates(df_pedidos: pd.DataFrame) -> pd.DataFrame:
        """
        Valida y corrige fechas de pedidos:
        - Convierte FechaPedido y FechaEntrega a datetime.
        - Elimina pedidos donde FechaEntrega < FechaPedido (fechas imposibles).
        - Reemplaza fechas nulas con la mediana o elimina el registro.

        Parameters
        ----------
        df_pedidos : pd.DataFrame
            DataFrame con columnas FechaPedido y FechaEntrega (opcional).

        Returns
        -------
        df_clean : pd.DataFrame
            DataFrame con fechas validadas y limpias.
        """
        df_clean = df_pedidos.copy()
        
        # Convertir a datetime
        if 'FechaPedido' in df_clean.columns:
            df_clean['FechaPedido'] = pd.to_datetime(df_clean['FechaPedido'], errors='coerce')
        
        if 'FechaEntrega' in df_clean.columns:
            df_clean['FechaEntrega'] = pd.to_datetime(df_clean['FechaEntrega'], errors='coerce')
        
        # Contar registros antes
        initial_count = len(df_clean)
        
        # Validar que FechaEntrega >= FechaPedido (si existen ambas)
        if 'FechaPedido' in df_clean.columns and 'FechaEntrega' in df_clean.columns:
            invalid_dates = df_clean['FechaEntrega'] < df_clean['FechaPedido']
            if invalid_dates.any():
                logger.warning(f"⚠️  {invalid_dates.sum()} pedidos con FechaEntrega < FechaPedido. Se eliminarán.")
                df_clean = df_clean[~invalid_dates]
        
        # Eliminar registros donde FechaPedido es nulo (es crítica)
        if 'FechaPedido' in df_clean.columns:
            null_pedido = df_clean['FechaPedido'].isna()
            if null_pedido.any():
                logger.warning(f"⚠️  {null_pedido.sum()} pedidos con FechaPedido nula. Se eliminarán.")
                df_clean = df_clean[~null_pedido]
        
        # Para FechaEntrega nula, intentar estimar (si es posible)
        if 'FechaEntrega' in df_clean.columns:
            null_entrega = df_clean['FechaEntrega'].isna()
            if null_entrega.any():
                logger.info(f"ℹ️  {null_entrega.sum()} pedidos con FechaEntrega nula. Asignando valor por defecto (+3 días).")
                df_clean.loc[null_entrega, 'FechaEntrega'] = df_clean.loc[null_entrega, 'FechaPedido'] + timedelta(days=3)
        
        removed_count = initial_count - len(df_clean)
        logger.info(f"✅ Validación de fechas: {removed_count} registros eliminados. Quedan {len(df_clean)} registros.")
        
        return df_clean

    @staticmethod
    def handle_null_metrics(df: pd.DataFrame, metric_columns: list = None) -> pd.DataFrame:
        """
        Reemplaza valores nulos en columnas de métricas (cantidad, precio, distancia, etc.)
        con la media de la columna. Si la media es NaN (columna toda nula), usa 0.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame a procesar.
        metric_columns : list, optional
            Lista de nombres de columnas a limpiar. Si es None, se detectan automáticamente.

        Returns
        -------
        df_clean : pd.DataFrame
            DataFrame con nulos reemplazados por promedios.
        """
        df_clean = df.copy()
        
        # Si no se especifican columnas, detectar automáticamente las columnas numéricas relevantes
        if metric_columns is None:
            metric_columns = [
                'Cantidad', 'PrecioVenta', 'distancia_km', 'Precio', 'PrecioUnitario'
            ]
            # Filtrar solo las que existen en el DataFrame
            metric_columns = [col for col in metric_columns if col in df_clean.columns]
        
        for col in metric_columns:
            if col in df_clean.columns:
                null_count = df_clean[col].isna().sum()
                if null_count > 0:
                    mean_val = df_clean[col].mean()
                    # Si la media es NaN (toda la columna es nula), usar 0
                    fill_value = mean_val if not pd.isna(mean_val) else 0
                    logger.info(f"ℹ️  {null_count} valores nulos en '{col}'. Reemplazando con media: {fill_value:.2f}")
                    df_clean[col] = df_clean[col].fillna(fill_value)
        
        return df_clean

    @staticmethod
    def validate_no_negatives(df: pd.DataFrame, numeric_columns: list = None) -> pd.DataFrame:
        """
        Valida y corrige valores negativos en columnas numéricas.
        Valores negativos se reemplazan con el valor absoluto (o 0 si es apropiado).

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame a procesar.
        numeric_columns : list, optional
            Lista de nombres de columnas a validar. Si es None, se validan todas las numéricas.

        Returns
        -------
        df_clean : pd.DataFrame
            DataFrame con valores negativos corregidos.
        """
        df_clean = df.copy()
        
        if numeric_columns is None:
            numeric_columns = df_clean.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in numeric_columns:
            if col in df_clean.columns:
                negative_mask = df_clean[col] < 0
                if negative_mask.any():
                    negative_count = negative_mask.sum()
                    logger.warning(f"⚠️  {negative_count} valores negativos en '{col}'. Convirtiendo a valor absoluto.")
                    df_clean.loc[negative_mask, col] = df_clean.loc[negative_mask, col].abs()
        
        return df_clean

    @staticmethod
    def remove_duplicate_rows(df: pd.DataFrame, subset: list = None) -> pd.DataFrame:
        """
        Elimina filas duplicadas del DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame a procesar.
        subset : list, optional
            Columnas a considerar para detectar duplicados. Si es None, usa todas.

        Returns
        -------
        df_clean : pd.DataFrame
            DataFrame sin duplicados.
        """
        initial_count = len(df)
        df_clean = df.drop_duplicates(subset=subset, keep='first')
        removed_count = initial_count - len(df_clean)
        
        if removed_count > 0:
            logger.info(f"ℹ  {removed_count} filas duplicadas eliminadas.")
        
        return df_clean

    @staticmethod
    def clean_full_dataset(clientes, destinos, lineas, pedidos, productos, provincias):
        """
        Ejecuta todas las limpiezas en cascada sobre el conjunto completo de datos.

        Parameters
        ----------
        clientes, destinos, lineas, pedidos, productos, provincias : pd.DataFrame
            DataFrames originales de la base de datos.

        Returns
        -------
        tuple
            Tupla con los DataFrames limpios: (clientes, destinos, lineas, pedidos, productos, provincias)
        """
        logger.info("=" * 60)
        logger.info("INICIANDO LIMPIEZA COMPLETA DE DATOS")
        logger.info("=" * 60)
        
        # 1. Limpiar espacios en blanco
        logger.info("\n1️⃣  Eliminando espacios en blanco en columnas de texto...")
        clientes = DataCleaner.clean_dataframe(clientes)
        destinos = DataCleaner.clean_dataframe(destinos)
        lineas = DataCleaner.clean_dataframe(lineas)
        pedidos = DataCleaner.clean_dataframe(pedidos)
        productos = DataCleaner.clean_dataframe(productos)
        provincias = DataCleaner.clean_dataframe(provincias)
        
        # 2. Eliminar duplicados
        logger.info("\n2️⃣  Eliminando filas duplicadas...")
        clientes = DataCleaner.remove_duplicate_rows(clientes)
        destinos = DataCleaner.remove_duplicate_rows(destinos)
        lineas = DataCleaner.remove_duplicate_rows(lineas)
        pedidos = DataCleaner.remove_duplicate_rows(pedidos)
        productos = DataCleaner.remove_duplicate_rows(productos)
        provincias = DataCleaner.remove_duplicate_rows(provincias)
        
        # 3. Validar y limpiar fechas (en pedidos)
        logger.info("\n3️⃣  Validando fechas en Pedidos...")
        pedidos = DataCleaner.validate_and_clean_dates(pedidos)
        
        # 4. Manejar nulos en métricas clave
        logger.info("\n4️⃣  Reemplazando nulos en columnas de métricas...")
        lineas = DataCleaner.handle_null_metrics(lineas, ['Cantidad', 'PrecioVenta'])
        productos = DataCleaner.handle_null_metrics(productos, ['Precio', 'PrecioVenta'])
        destinos = DataCleaner.handle_null_metrics(destinos, ['distancia_km'])
        
        # 5. Validar valores no negativos
        logger.info("\n5️⃣  Validando que no haya valores negativos...")
        lineas = DataCleaner.validate_no_negatives(lineas, ['Cantidad', 'PrecioVenta'])
        productos = DataCleaner.validate_no_negatives(productos, ['Precio', 'PrecioVenta'])
        destinos = DataCleaner.validate_no_negatives(destinos, ['distancia_km'])
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ LIMPIEZA COMPLETADA EXITOSAMENTE")
        logger.info("=" * 60 + "\n")
        
        return clientes, destinos, lineas, pedidos, productos, provincias