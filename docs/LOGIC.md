# 🧠 Lógica Algorítmica

Este documento detalla los dos motores de inteligencia artificial que impulsan IA Delivery.

## 1. Algoritmo de Clustering (Agrupación)
Utilizamos un enfoque **K-Means modificado** con restricciones de capacidad (*Capacitated Clustering*).

* **Objetivo:** Agrupar pedidos cercanos geográficamente.
* **Restricción Dura:** La suma del peso (`Peso_Total_Kg`) de los pedidos en un grupo NO puede superar la capacidad máxima del vehículo asignado.
* **Gestión de Descartes:** Si un clúster excede la capacidad, los pedidos más alejados del centroide (outliers) son expulsados y enviados al **Backlog de Capacidad**.

## 2. Algoritmo de Routing (Enrutamiento)
Implementamos una heurística *Greedy* (Voraz) enriquecida con simulación temporal compleja.

### El "Tacógrafo Virtual"
El sistema simula el comportamiento legal de un conductor de camión en tiempo real:

1.  **Límite de Conducción:** Se permite un máximo de **8 horas** (480 minutos) de conducción continua.
2.  **Descanso Obligatorio:** Al superar las 8 horas acumuladas, el algoritmo inserta automáticamente una penalización de **12 horas** (720 minutos) de descanso.
3.  **Validación de Caducidad (Time Windows):** * Al llegar a cada cliente, se calcula: `Hora_Salida + Tiempo_Viaje + (Descansos)`.
    * Si `Hora_Llegada > Fecha_Limite_Entrega` del pedido, el algoritmo **descarta el pedido**.
    * Estos pedidos forman el **Backlog de Tiempo** (Caducados).

### Geometría Real
No utilizamos distancia euclidiana (línea recta). Las distancias y tiempos se consultan contra la API de **OSRM**, garantizando que las rutas sigan la red de carreteras real.