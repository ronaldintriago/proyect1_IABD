# 🏗️ Arquitectura del Sistema

**IA Delivery** sigue una arquitectura modular basada en el patrón **MVC (Modelo-Vista-Controlador)** adaptado a pipelines de datos.

## Diagrama de Flujo de Datos

El sistema opera en un flujo lineal determinista:

1.  **Ingesta:** Se cargan datos desde SQL Server. Si la conexión falla, se activa el *fallback* a CSVs locales (`data/raw`).
2.  **Normalización (ETL):** Se limpian duplicados, se validan fechas y se geocodifican direcciones usando `geopy`.
3.  **Procesamiento (Model):** * Se generan clusters de pedidos.
    * Se calculan rutas óptimas.
4.  **Visualización (View):** Se renderizan los resultados en un mapa interactivo.

## Stack Tecnológico

* **Lenguaje:** Python 3.13+
* **Gestión de Paquetes:** `uv` (Astral)
* **Interfaz:** Streamlit
* **Visualización Geoespacial:** Folium + Leaflet
* **Motor de Routing:** OSRM (Open Source Routing Machine) API
* **Base de Datos:** Microsoft SQL Server (con Driver ODBC 18)

## Patrones de Diseño

* **Strategy:** Utilizado en el servicio de Clustering para alternar entre el modo "Recursos Finitos" (Manual) y "Recursos Infinitos" (Ideal).
* **Singleton:** Aplicado en la configuración de base de datos (`DBConfig`) para mantener una única referencia de conexión.
* **Facade:** El `LogisticsController` simplifica la complejidad del sistema presentando métodos simples (`ejecutar_calculo`) a la interfaz.