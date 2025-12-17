import pandas as pd
import os
from sqlalchemy import create_engine
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

geolocator = Nominatim(user_agent="app")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def geocode_province(name):
    try:
        location = geocode(name)
        if location:
            return pd.Series([location.latitude, location.longitude])
        else:
            return pd.Series([None, None])
    except Exception:
        return pd.Series([None, None])

# --- FUNCIONES DE AYUDA ---

def load_or_create_provincia_geo(provincias_df, csv_path="src/data/provincias_geo.csv"):
    print("🌍 Geocoding provinces... this will take some time...")

    # Apply geocoding
    provincias_df[['Latitud', 'Longitud']] = provincias_df['nombre'].apply(geocode_province)

    # Save to CSV
    provincias_df.to_csv(csv_path, index=False)
    print("💾 Provinces geolocation saved in:", csv_path)

    return provincias_df



# --- FUNCIÓN DE CARGA ---
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

        print('Connection to database OK')
        
        # Consultas SQL
        df_provincias = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Provincias", engine)

        print('Provincias dataframe obtained')

        return df_provincias

    except Exception as e:
        print(e)

provincias = cargar_datos_sql()

load_or_create_provincia_geo(provincias)
