import pandas as pd
from sqlalchemy import create_engine
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

# Database connection
server = '10.0.40.12' 
port = '1433'
database = 'master'
username = 'sa'
password = 'Stucom.2025'

connection_url = (
    f"mssql+pyodbc://{username}:{password}@{server}:{port}/{database}"
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&Encrypt=no&TrustServerCertificate=yes"
)

try:
    engine = create_engine(connection_url)
    
    # Load data from database
    print("Loading data from database...")
    df_destinos = pd.read_sql(
        "SELECT DestinoID, nombre_completo, distancia_km, provinciaID FROM BDIADelivery.dbo.Destinos", 
        engine
    )
    df_clients = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Clientes", engine)
    df_orders = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Pedidos", engine)
    df_lineOrders = pd.read_sql("SELECT * FROM BDIADelivery.dbo.LineasPedido", engine)
    df_products = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Productos", engine)
    df_provinces = pd.read_sql("SELECT * FROM BDIADelivery.dbo.Provincias", engine)
    
    print(f"Data loaded successfully!")
    print(f"Orders: {len(df_orders)}, Clients: {len(df_clients)}, Products: {len(df_products)}")
    
    # Remove duplicates
    df_destinos = df_destinos.drop_duplicates()
    df_clients = df_clients.drop_duplicates()
    df_orders = df_orders.drop_duplicates()
    df_lineOrders = df_lineOrders.drop_duplicates()
    df_products = df_products.drop_duplicates()
    df_provinces = df_provinces.drop_duplicates()
    
    # Convert date column if it's not already datetime
    if 'FechaPedido' in df_orders.columns:
        df_orders['FechaPedido'] = pd.to_datetime(df_orders['FechaPedido'])
    
    # Create comprehensive merged dataframe with CORRECT join keys
    # First merge orders with clients
    df_full = df_orders.merge(df_clients, on="ClienteID", how="left", suffixes=('', '_client'))
    
    # Then merge with destinos (which contains provinciaID)
    df_full = df_full.merge(df_destinos, left_on="DestinoEntregaID", right_on="DestinoID", how="left")

    print(df_full.head())
    
    # Now we can merge with provinces using the provinciaID from destinos
    df_full = df_full.merge(df_provinces, left_on="provinciaID", right_on="ProvinciaID", how="left", suffixes=('', '_prov'))
    
    # Add order line items and products
    df_full_with_products = (
        df_full
        .merge(df_lineOrders, on="PedidoID", how="left")
        .merge(df_products, on="ProductoID", how="left", suffixes=('', '_prod'))
    )
    
    print(f"\nMerged dataframe shape: {df_full_with_products.shape}")
    print(f"Columns: {df_full_with_products.columns.tolist()}")
    
    # Select only numeric columns for correlation
    numeric_df = df_full_with_products.select_dtypes(include=['int64', 'float64', 'int32', 'float32'])
    
    print(f"\nNumeric columns for correlation: {numeric_df.columns.tolist()}")
    
    # Calculate correlation matrix
    correlation_matrix = numeric_df.corr()
    
    # Create visualizations
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle('Database Analytics Dashboard', fontsize=16, fontweight='bold')
    
    # 1. Correlation Heatmap
    ax1 = axes[0, 0]
    sns.heatmap(correlation_matrix, annot=True, fmt='.2f', cmap="coolwarm", 
                center=0, ax=ax1, cbar_kws={'label': 'Correlation'})
    ax1.set_title('Correlation Matrix (All Numeric Variables)', fontsize=12, fontweight='bold')
    ax1.tick_params(axis='x', rotation=45)
    ax1.tick_params(axis='y', rotation=0)
    
    # 2. Top correlations (excluding diagonal)
    ax2 = axes[0, 1]
    corr_pairs = correlation_matrix.unstack()
    corr_pairs = corr_pairs[corr_pairs != 1.0]  # Remove self-correlations
    top_corr = corr_pairs.abs().sort_values(ascending=False).head(15)
    
    y_pos = np.arange(len(top_corr))
    colors = ['green' if corr_pairs[idx] > 0 else 'red' for idx in top_corr.index]
    ax2.barh(y_pos, [corr_pairs[idx] for idx in top_corr.index], color=colors, alpha=0.7)
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([f"{idx[0][:15]} vs {idx[1][:15]}" for idx in top_corr.index], fontsize=8)
    ax2.set_xlabel('Correlation Coefficient')
    ax2.set_title('Top 15 Strongest Correlations', fontsize=12, fontweight='bold')
    ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
    ax2.grid(axis='x', alpha=0.3)
    
    # 3. Distribution of distances
    ax3 = axes[1, 0]
    if 'distancia_km' in df_full.columns:
        ax3.hist(df_full['distancia_km'].dropna(), bins=30, color='skyblue', edgecolor='black', alpha=0.7)
        ax3.set_xlabel('Distance (km)')
        ax3.set_ylabel('Frequency')
        ax3.set_title('Distribution of Delivery Distances', fontsize=12, fontweight='bold')
        ax3.grid(axis='y', alpha=0.3)
    
    # 4. Orders over time
    ax4 = axes[1, 1]
    if 'FechaPedido' in df_orders.columns:
        orders_by_date = df_orders.groupby(df_orders['FechaPedido'].dt.date).size()
        ax4.plot(orders_by_date.index, orders_by_date.values, marker='o', linewidth=2, markersize=4)
        ax4.set_xlabel('Date')
        ax4.set_ylabel('Number of Orders')
        ax4.set_title('Orders Timeline', fontsize=12, fontweight='bold')
        ax4.tick_params(axis='x', rotation=45)
        ax4.grid(alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print key insights
    print("\n" + "="*60)
    print("KEY CORRELATION INSIGHTS")
    print("="*60)
    
    print("\nTop 10 Positive Correlations:")
    positive_corr = corr_pairs[corr_pairs > 0].sort_values(ascending=False).head(10)
    for idx, val in positive_corr.items():
        print(f"  • {idx[0]} ↔ {idx[1]}: {val:.3f}")
    
    print("\nTop 10 Negative Correlations:")
    negative_corr = corr_pairs[corr_pairs < 0].sort_values().head(10)
    for idx, val in negative_corr.items():
        print(f"  • {idx[0]} ↔ {idx[1]}: {val:.3f}")
    
    # Summary statistics
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    print(numeric_df.describe())
    
    # Check for missing values
    print("\n" + "="*60)
    print("MISSING VALUES")
    print("="*60)
    missing = df_full_with_products.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if len(missing) > 0:
        print(missing)
    else:
        print("No missing values found!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()