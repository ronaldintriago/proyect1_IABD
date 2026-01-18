


# FECHA BASE DE LA SIMULACIÓN
SIMULATION_START_DATE = "2025-12-15 08:00:00"

# Definición de la Flota con parámetros ECONÓMICOS
# Costes estimados para logística en España 

FLEET_CONFIG = {
    1: {
        "nombre": "Furgoneta Eco",
        "capacidad_kg": 500,
        "velocidad_media_kmh": 90,
        "coste_fijo_por_viaje": 120,    
        "coste_variable_por_km": 0.25
    },
    2: {
        "nombre": "Furgoneta Estándar",
        "capacidad_kg": 1200,
        "velocidad_media_kmh": 80,
        "coste_fijo_por_viaje": 150,
        "coste_variable_por_km": 0.35
    },
    3: {
        "nombre": "Camión Rígido",
        "capacidad_kg": 8000,
        "velocidad_media_kmh": 70,
        "coste_fijo_por_viaje": 250,
        "coste_variable_por_km": 0.65
    },
    4: {
        "nombre": "Tráiler Pesado",
        "capacidad_kg": 25000,
        "velocidad_media_kmh": 60,
        "coste_fijo_por_viaje": 350,
        "coste_variable_por_km": 0.95
    }
}