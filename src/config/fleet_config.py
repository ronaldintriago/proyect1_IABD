


# FECHA BASE DE LA SIMULACIÓN
# Fingimos que "Hoy" es este día para que los pedidos de dic-2025 sean válidos
SIMULATION_START_DATE = "2025-12-15 08:00:00"

# Definición de la Flota con parámetros ECONÓMICOS
# Costes estimados para logística en España (Ejemplo)

FLEET_CONFIG = {
    1: {
        "nombre": "Furgoneta Eco",
        "capacidad_kg": 500,
        "velocidad_media_kmh": 90,
        "coste_fijo_por_viaje": 120,    # Conductor (media jornada/ruta corta) + Vehículo
        "coste_variable_por_km": 0.25   # Poco consumo
    },
    2: {
        "nombre": "Furgoneta Estándar",
        "capacidad_kg": 1200,
        "velocidad_media_kmh": 80,
        "coste_fijo_por_viaje": 150,    # Conductor + Vehículo
        "coste_variable_por_km": 0.35
    },
    3: {
        "nombre": "Camión Rígido",
        "capacidad_kg": 8000,
        "velocidad_media_kmh": 70,
        "coste_fijo_por_viaje": 250,    # Conductor C + Vehículo más caro
        "coste_variable_por_km": 0.65   # Consumo medio-alto
    },
    4: {
        "nombre": "Tráiler Pesado",
        "capacidad_kg": 25000,
        "velocidad_media_kmh": 60,
        "coste_fijo_por_viaje": 350,    # Conductor C+E + Cabeza tractora
        "coste_variable_por_km": 0.95   # Alto consumo + Peajes
    }
}