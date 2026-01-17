# 🚛 IA Delivery: Sistema de Optimización Logística

![Python](https://img.shields.io/badge/Python-3.13%2B-blue)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)
![ML](https://img.shields.io/badge/AI-KMeans%20%7C%20PuLP-green)
![Status](https://img.shields.io/badge/Status-MVP%20Complete-success)

**IA Delivery** es un sistema inteligente de optimización de rutas (VRP) diseñado para minimizar costes logísticos en el transporte de mercancías perecederas.

El sistema utiliza un enfoque híbrido **"Cluster-First, Route-Second"** para gestionar flotas heterogéneas, garantizando el cumplimiento de ventanas de tiempo (caducidad) y restricciones de capacidad, proporcionando además una **auditoría económica** de la flota actual frente a la ideal.


## 📚 Documentación

Para mantener este archivo limpio, la documentación técnica detallada se encuentra en la carpeta `/docs`:

* 📂 **[Estructura del Proyecto](docs/STRUCTURE.md):** Organización de carpetas y módulos.
* 🏗️ **[Arquitectura](docs/ARCHITECTURE.md):** Flujo de datos, stack tecnológico y patrones.
* 🧠 **[Lógica Algorítmica](docs/LOGIC.md):** Explicación del Clustering y el simulador de Tacógrafo.
* 📊 **[Resultados](docs/RESULTS.md):** Interpretación de métricas y dashboard.
* 📖 **[Manual de Usuario](docs/USER_GUIDE.md):** Guía paso a paso para usar la aplicación.

---

## 🚀 Inicio Rápido

### Requisitos
* Python 3.13+
* [uv](https://github.com/astral-sh/uv) (Recomendado)

### Ejecución
```bash

Este proyecto utiliza **[uv](https://github.com/astral-sh/uv)** para una gestión de dependencias ultrarrápida.

### 1️⃣ Instalación

Clona el repositorio e instala las dependencias:

```bash
# Clonar repositorio
git clone [https://github.com/tu-usuario/ia-delivery.git](https://github.com/tu-usuario/ia-delivery.git)

# Crear entorno virtual y sincronizar dependencias
uv sync

#  Ejecutar la aplicación
uv run streamlit run main.py