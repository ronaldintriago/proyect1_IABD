import os
import logging
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from src.etl.db_loader import DataLoader

logger = logging.getLogger(__name__)

# Geocoder (used only as fallback)
geolocator = Nominatim(user_agent="app")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)


def geocode_name(name):
    try:
        location = geocode(name)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        logger.warning("Geocoding failed for %s: %s", name, e)
        return None, None


def ensure_provincias_geo(provincias_df: pd.DataFrame, csv_path: str = "data/raw/provincias_geo.csv") -> pd.DataFrame:
    """Asegura que `provincias_df` contiene columnas Latitud y Longitud.

    Si existe un CSV con las coordenadas lo carga; si no, intenta geocodificar
    por nombre de provincia y guarda el CSV para uso futuro.
    """
    # Priorizar archivo CSV si existe
    if os.path.exists(csv_path):
        try:
            prov_geo = pd.read_csv(csv_path)
            # Hacer merge para mantener ProvinciaID y nombre originales
            merged = provincias_df.merge(prov_geo[['ProvinciaID', 'Latitud', 'Longitud']], on='ProvinciaID', how='left')
            logger.info("Loaded province coordinates from %s", csv_path)
            return merged
        except Exception as e:
            logger.warning("Failed loading existing provincias geo CSV: %s", e)

    # Si no hay CSV o falla, intentamos geocodificar
    logger.info("Geocoding provinces (this can take a while)...")
    latitudes = []
    longitudes = []
    for name in provincias_df['nombre'].astype(str).tolist():
        lat, lon = geocode_name(name)
        latitudes.append(lat)
        longitudes.append(lon)

    provincias_df = provincias_df.copy()
    provincias_df['Latitud'] = latitudes
    provincias_df['Longitud'] = longitudes

    # Guardar CSV para uso futuro
    try:
        provincias_df.to_csv(csv_path, index=False)
        logger.info("Saved provincias geolocation to %s", csv_path)
    except Exception as e:
        logger.warning("Could not save provincias geo CSV: %s", e)

    return provincias_df


def add_coordinates_to_destinos(destinos_df: pd.DataFrame, provincias_df: pd.DataFrame) -> pd.DataFrame:
    """Añade una columna `coordenadas` a `destinos_df` con (lat, lon).

    Lógica:
    - Si `destinos_df` ya contiene coordenadas (col `coordenadas_gps` o `lat`/`lon`), las utiliza.
    - Si no, intenta mapear desde `provincias_df` a través de `provinciaID` / `ProvinciaID`.
    - Si sigue sin coordenadas, intenta geocodificar `nombre_completo` del destino como fallback.
    """
    dest = destinos_df.copy()
    prov = provincias_df.copy()

    # Normalizar tipos de ID para merge seguro
    if 'provinciaID' in dest.columns:
        dest['provinciaID'] = pd.to_numeric(dest['provinciaID'], errors='coerce')
    if 'ProvinciaID' in prov.columns:
        prov['ProvinciaID'] = pd.to_numeric(prov['ProvinciaID'], errors='coerce')

    # Primero intentamos parsear campo 'coordenadas_gps' si existe (ej: "lat,lon" o "(lat, lon)")
    def parse_gps(val):
        if pd.isna(val):
            return None
        try:
            s = str(val)
            s = s.strip().replace('(', '').replace(')', '')
            parts = [p.strip() for p in s.split(',')]
            if len(parts) >= 2:
                lat = float(parts[0])
                lon = float(parts[1])
                return (lat, lon)
        except Exception:
            return None
        return None

    dest['coordenadas'] = dest.get('coordenadas_gps', None).apply(parse_gps) if 'coordenadas_gps' in dest.columns else None

    # Segundo: mapear desde provincias
    prov_coords = prov.set_index('ProvinciaID')[['Latitud', 'Longitud']].to_dict(orient='index')

    def fill_from_prov(row):
        if row.get('coordenadas'):
            return row['coordenadas']
        pid = row.get('provinciaID')
        if pd.isna(pid):
            return None
        coords = prov_coords.get(int(pid)) if int(pid) in prov_coords else None
        if coords and not pd.isna(coords.get('Latitud')):
            return (float(coords['Latitud']), float(coords['Longitud']))
        return None

    # Apply mapping
    dest['coordenadas'] = dest.apply(lambda r: fill_from_prov(r) if not r.get('coordenadas') else r['coordenadas'], axis=1)

    # Tercero: fallback geocoding por nombre completo de destino
    need_geocode = dest['coordenadas'].isna()
    if need_geocode.any():
        logger.info("Geocoding %d destinos as fallback...", need_geocode.sum())
        for idx in dest[need_geocode].index:
            name = dest.at[idx, 'nombre_completo'] if 'nombre_completo' in dest.columns else None
            if name:
                lat, lon = geocode_name(name)
                if lat is not None:
                    dest.at[idx, 'coordenadas'] = (lat, lon)

    return dest


def enrich_destinos_with_coords(csv_cache='data/raw/provincias_geo.csv') -> pd.DataFrame:
    """Carga datos limpios desde `DataLoader`, asegura coordenadas y devuelve `destinos` enriquecido."""
    clientes, destinos, lineas, pedidos, productos, provincias = DataLoader.load_data()

    provincias_geo = ensure_provincias_geo(provincias, csv_path=csv_cache)
    destinos_with_coords = add_coordinates_to_destinos(destinos, provincias_geo)

    logger.info("Destinos enriched with coordenadas. Total: %d", len(destinos_with_coords))
    return destinos_with_coords


if __name__ == "__main__":
    # Ejecutable para desarrollo/local: imprime un resumen de destinos con coordenadas
    dest = enrich_destinos_with_coords()
    print(dest[['DestinoID', 'nombre_completo', 'coordenadas']].head(30).to_string())
