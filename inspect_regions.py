import geopandas as gpd
import pandas as pd

shp_path = "data/shapefiles/ne_10m_admin_1_states_provinces.shp"
gdf = gpd.read_file(shp_path)

print("Columns:", gdf.columns)

# Filter for France
france_regions = gdf[gdf['admin'] == 'France']

if france_regions.empty:
    print("No regions found with admin='France'. Checking 'geonunit'...")
    france_regions = gdf[gdf['geonunit'] == 'France']

print(f"Found {len(france_regions)} regions for France:")
for index, row in france_regions.iterrows():
    print(f"Name: {row['name']}, WOE_Name: {row.get('woe_name')}, GN_Name: {row.get('gn_name')}")
