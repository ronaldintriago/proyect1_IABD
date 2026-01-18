# 📂 Estructura del Proyecto

Este documento detalla la organización de directorios y la responsabilidad de cada módulo en **IA Delivery**.

## Árbol de Directorios

```text
PROYECT1_IABD/
├── 📂 data/                    # CAPA DE PERSISTENCIA
│   ├── 📂 raw/                 # Datos de origen (CSVs o dumps SQL)
│   └── 📂 processed/           # Datos generados por el sistema (Maestro y Clusters)
│
├── 📂 src/                     # CÓDIGO FUENTE
│   ├── 📂 config/              # Parámetros Globales
│   │   ├── db_config.py        # Credenciales SQL Server
│   │   └── fleet_config.py     # Costes y capacidades de vehículos
│   │
│   ├── 📂 controllers/         # Orquestación
│   │   ├── main_controller.py  # Controlador principal (Facade)
│   │   └── clustering_runner.py# Ejecutor de procesos batch
│   │
│   ├── 📂 etl/                 # Ingeniería de Datos
│   │   ├── clean_data.py       # Limpieza y validación de tipos
│   │   ├── db_loader.py        # Carga híbrida (SQL/CSV)
│   │   ├── feature.py          # Generación del Dataset Maestro
│   │   └── load_coords.py      # Geocodificación (Nominatim)
│   │
│   ├── 📂 models/              # Lógica de IA
│   │   ├── clustering_service.py # Algoritmo de agrupación
│   │   └── routing.py          # Algoritmo de rutas y tacógrafo
│   │
│   ├── 📂 ui/                  # Frontend
│   │   └── streamlit_interface.py # Dashboard web
│   │
│   └── 📂 utils/               # Utilidades
│       └── map_renderer.py     # Motor gráfico (Folium + OSRM)
│
├── main.py                     # Punto de entrada
├── pyproject.toml              # Dependencias (uv)
└── uv.lock                     # Lockfile de versiones