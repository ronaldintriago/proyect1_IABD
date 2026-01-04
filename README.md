# 🚛 IA Delivery: Sistema de Optimización Logística

![Python](https://img.shields.io/badge/Python-3.13%2B-blue)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)
![ML](https://img.shields.io/badge/AI-KMeans%20%7C%20PuLP-green)
![Status](https://img.shields.io/badge/Status-MVP%20Complete-success)

**IA Delivery** es un sistema inteligente de optimización de rutas (VRP) diseñado para minimizar costes logísticos en el transporte de mercancías perecederas.

El sistema utiliza un enfoque híbrido **"Cluster-First, Route-Second"** para gestionar flotas heterogéneas, garantizando el cumplimiento de ventanas de tiempo (caducidad) y restricciones de capacidad, proporcionando además una **auditoría económica** de la flota actual frente a la ideal.

---

## 🏗️ Arquitectura del Proyecto

El proyecto sigue una arquitectura **MVC (Modelo-Vista-Controlador)** modularizada para separar la lógica de negocio, la algoritmia y la visualización.

* **Data Layer (`data/`):** ETL robusto que normaliza datos de SQL Server/CSV y genera un Dataset Maestro geolocalizado.
* **Model Layer (`src/models/`):**
    * *Clustering Estratégico:* Algoritmo K-Means adaptativo con restricciones de negocio (Peso/Paradas) y cerebro económico.
    * *Routing Táctico:* Solucionador exacto (PuLP/OR-Tools) para la secuencia óptima de entrega.
* **Controller Layer (`src/controllers/`):** Orquestador que conecta los datos con los algoritmos.
* **Presentation Layer (`src/ui/`):** Dashboard interactivo en Streamlit para la toma de decisiones.

---

## 📂 Estructura del Proyecto

    PROJECT1_IABD/
    ├── 📂 assets/              # Recursos estáticos (imágenes, logos)
    ├── 📂 data/                # Data Lake (Fuera del código fuente)
    │   ├── 📂 raw/             # CSVs originales (Clientes, Pedidos, etc.)
    │   └── 📂 processed/       # Datasets maestros y resultados del modelo
    ├── 📂 src/                 # Código Fuente Principal
    │   ├── 📂 config/          # Configuraciones (DB, Flota, Constantes)
    │   ├── 📂 controllers/     # Lógica de Orquestación (Main Controller)
    │   ├── 📂 data/            # Scripts de ETL y Limpieza (Cleaners, Loaders)
    │   ├── 📂 models/          # Algoritmos de IA (Clustering & Routing)
    │   └── 📂 ui/              # Interfaz de Usuario (Streamlit)
    ├── main.py                 # Punto de entrada de la aplicación
    ├── pyproject.toml          # Dependencias (uv)
    └── README.md               # Documentación

---

## 🚀 Guía de Inicio Rápido

Este proyecto utiliza **[uv](https://github.com/astral-sh/uv)** para una gestión de dependencias ultrarrápida.

### 1️⃣ Instalación

Clona el repositorio e instala las dependencias:

```bash
# Clonar repositorio
git clone [https://github.com/tu-usuario/ia-delivery.git](https://github.com/tu-usuario/ia-delivery.git)

# Crear entorno virtual y sincronizar dependencias
uv sync