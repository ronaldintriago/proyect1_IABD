import plotly.express as px
import pandas as pd

class AuditPlotter:
    
    @staticmethod
    def plot_clustering_zones(rutas):
        """
        Genera el mapa estático de zonas (Clustering).
        """
        puntos_cluster = []
        for r in rutas:
            for p in r.get('ruta', []):
                puntos_cluster.append({
                    'Latitud': p.get('Latitud'),
                    'Longitud': p.get('Longitud'),
                    'Zona': f"C{r['cluster_id']} ({r['vehiculo']})",
                    'Cliente': p.get('nombre_completo')
                })
        
        if not puntos_cluster:
            return None

        df_clust = pd.DataFrame(puntos_cluster)
        
        fig = px.scatter_mapbox(
            df_clust, 
            lat="Latitud", 
            lon="Longitud", 
            color="Zona",
            hover_name="Cliente", 
            zoom=5, 
            height=500
        )
        fig.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
        return fig

    @staticmethod
    def plot_routing_animation(rutas):
        """
        Genera la animación global de todas las rutas simultáneas.
        """
        # 1. Preparar estructura de datos
        veh_histories = {}
        max_steps = 0
        
        for r in rutas:
            raw_hist = r.get('audit_history', [])
            if not raw_hist: continue
            
            # Agrupar por step_index
            steps_dict = {}
            for item in raw_hist:
                s_idx = item['step_index']
                if s_idx not in steps_dict: steps_dict[s_idx] = []
                steps_dict[s_idx].append(item)
                if s_idx > max_steps: max_steps = s_idx
            
            veh_id = f"{r['vehiculo']} #{r['cluster_id']}"
            veh_histories[veh_id] = steps_dict

        if max_steps == 0:
            return None

        # 2. Sincronizar Frames (Rellenar huecos)
        combined_rows = []
        for s in range(max_steps + 1):
            for v_name, v_steps in veh_histories.items():
                current_data = []
                if s in v_steps:
                    current_data = v_steps[s]
                else:
                    # Si el camión acabó antes, se queda quieto en su última posición
                    last_step = max([k for k in v_steps.keys() if k < s], default=0)
                    current_data = v_steps.get(last_step, [])
                
                for item in current_data:
                    row = item.copy()
                    row['Time_Step'] = s
                    row['Vehiculo_ID'] = v_name
                    combined_rows.append(row)
        
        if not combined_rows:
            return None

        df_anim = pd.DataFrame(combined_rows)
        
        # 3. Generar Plotly
        fig = px.line_mapbox(
            df_anim,
            lat="Latitud",
            lon="Longitud",
            color="Vehiculo_ID",
            animation_frame="Time_Step",
            animation_group="Vehiculo_ID",
            zoom=5, 
            height=600
        )
        
        # Puntos de referencia
        fig.add_scattermapbox(
            lat=df_anim["Latitud"], lon=df_anim["Longitud"],
            mode='markers', marker=dict(size=6, opacity=0.8), showlegend=False,
            hoverinfo='text', text=df_anim['nombre_completo']
        )
        
        fig.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
        return fig