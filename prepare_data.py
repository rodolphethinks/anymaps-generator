import os
import zipfile
import requests
import geopandas as gpd
# import elevation 
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
import shapely
import numpy as np
from pathlib import Path
import shutil
import math
import json
from PIL import Image

# Config
DATA_DIR = Path("data")
EXISTING_CACHE_DIR = Path("../map_render/data/dem/srtm_cache_tif").resolve() 
SHAPEFILE_URL = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip"
COUNTRY_NAME = "South Korea"

def setup_directories():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "shapefiles").mkdir(exist_ok=True)
    (DATA_DIR / "dem").mkdir(exist_ok=True)
    EXISTING_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def download_shapefile():
    target_zip = DATA_DIR / "shapefiles" / "ne_10m_admin_0_countries.zip"
    target_shp = DATA_DIR / "shapefiles" / "ne_10m_admin_0_countries.shp"
    
    if target_shp.exists():
        print(f"Shapefile already exists at {target_shp}")
        return target_shp

    print(f"Downloading shapefile from {SHAPEFILE_URL}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(SHAPEFILE_URL, headers=headers, stream=True)
        if response.status_code == 200:
            with open(target_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
            print("Download complete. Extracting...")
            with zipfile.ZipFile(target_zip, 'r') as zip_ref:
                zip_ref.extractall(DATA_DIR / "shapefiles")
        else:
            print(f"Download failed: {response.status_code}")
    except Exception as e:
        print(f"Error downloading shapefile: {e}")
        
    return target_shp

def get_country_geometry(shp_path, country_name):
    print(f"Loading shapefile to find {country_name}...")
    gdf = gpd.read_file(shp_path)
    # Check for name in standard columns
    country = gdf[gdf['ADMIN'] == country_name]
    if country.empty:
        country = gdf[gdf['NAME'] == country_name]
    
    if country.empty:
        raise ValueError(f"Country '{country_name}' not found in shapefile.")
    
    print(f"Found {country_name}. Getting geometry...")
    return country.iloc[0].geometry, country.iloc[0]

def get_cgiar_tiles(minx, miny, maxx, maxy):
    tiles = []
    # CGIAR grid: 5x5 degrees.
    # X matches logic from srtm.csi.cgiar.org
    # x = (lon + 180) // 5 + 1
    # y = (60 - lat) // 5 + 1
    
    # Ensure bounds are within global limits
    minx = max(-180, minx)
    maxx = min(180, maxx)
    miny = max(-60, miny)
    maxy = min(60, maxy)

    start_x = int((minx + 180) // 5) + 1
    end_x = int((maxx + 180) // 5) + 1
    
    # Y index: Top is Y=1 (60 deg N), Bottom is Y=24 (-60 S)
    # y = (60 - lat) / 5
    # Max Lat corresponds to Min Y index (Higher up)
    start_y = int((60 - maxy) // 5) + 1
    end_y = int((60 - miny) // 5) + 1
    
    for x in range(start_x, end_x + 1):
        for y in range(start_y, end_y + 1):
            tiles.append((x, y))
    
    return tiles

def download_dem_manual(geometry, country_name):
    bounds = geometry.bounds 
    print(f"Bounds: {bounds}")
    
    minx, miny, maxx, maxy = bounds
    tiles = get_cgiar_tiles(minx, miny, maxx, maxy)
    downloaded_tiffs = []
    
    print(f"Required Tiles (CGIAR 5x5): {tiles}")
    
    headers = {'User-Agent': 'Mozilla/5.0'}

    for x, y in tiles:
        filename = f"srtm_{x:02d}_{y:02d}"
        zip_name = f"{filename}.zip"
        tif_name = f"{filename}.tif"
        
        local_zip = EXISTING_CACHE_DIR / zip_name
        local_tif = EXISTING_CACHE_DIR / tif_name
        
        # Check if TIF exists
        if local_tif.exists():
             print(f"Tile {tif_name} found in cache.")
             downloaded_tiffs.append(local_tif)
             continue
             
        # Download Zip
        url = f"https://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF/{zip_name}"
        print(f"Downloading {url}...")
        try:
             response = requests.get(url, headers=headers, stream=True)
             if response.status_code == 200:
                with open(local_zip, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        f.write(chunk)
                
                print(f"Extracting {zip_name}...")
                with zipfile.ZipFile(local_zip, 'r') as zip_ref:
                    zip_ref.extract(tif_name, path=EXISTING_CACHE_DIR)
                
                downloaded_tiffs.append(local_tif)
                # Cleanup zip
                if local_zip.exists():
                    local_zip.unlink()
             else:
                 print(f"Failed to download {url} (Status {response.status_code})")
        except Exception as e:
             print(f"Exception downloading {url}: {e}")
             continue
    
    if not downloaded_tiffs:
        # Fallback loop - check if we downloaded anything this session or previous
        # Re-check cache
        downloaded_tiffs = []
        for x, y in tiles:
             tif_name = f"srtm_{x:02d}_{y:02d}.tif"
             local_tif = EXISTING_CACHE_DIR / tif_name
             if local_tif.exists():
                  downloaded_tiffs.append(local_tif)
        
        if not downloaded_tiffs:
            raise Exception("No DEM tiles available for merging.")

    # Merge
    print("Merging tiles...")
    src_files_to_mosaic = []
    opened_files = [] 
    for fp in downloaded_tiffs:
        try:
            src = rasterio.open(fp)
            src_files_to_mosaic.append(src)
            opened_files.append(src)
        except Exception as e:
            print(f"Could not open {fp}: {e}")

    if not src_files_to_mosaic:
        raise Exception("No valid raster files to merge.")

    mosaic, out_trans = merge(src_files_to_mosaic)
    
    # Close files
    for src in opened_files:
        src.close()
    
    # Update metadata
    out_meta = src_files_to_mosaic[0].meta.copy()
    out_meta.update({"driver": "GTiff",
                     "height": mosaic.shape[1],
                     "width": mosaic.shape[2],
                     "transform": out_trans})
                     
    output_path = DATA_DIR / "dem" / f"{country_name}_merged.tif"
    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(mosaic)
    
    print(f"Merged DEM saved to {output_path}")
    return output_path

def clip_dem(dem_path, geometry, country_name):
    print(f"Clipping DEM to {country_name} shape...")
    with rasterio.open(dem_path) as src:
        out_image, out_transform = mask(src, [geometry], crop=True)
        out_meta = src.meta.copy()
        
    out_meta.update({"driver": "GTiff",
                     "height": out_image.shape[1],
                     "width": out_image.shape[2],
                     "transform": out_transform})
                     
    clipped_path = DATA_DIR / "dem" / f"{country_name}_clipped.tif"
    with rasterio.open(clipped_path, "w", **out_meta) as dest:
        dest.write(out_image)
        
    print(f"Clipped DEM saved to {clipped_path}")
    return clipped_path

def export_for_blender(dem_path, geometry, attributes, country_name):
    print("Exporting for Blender...")
    with rasterio.open(dem_path) as src:
        data = src.read(1)
        
        # Stats
        min_elev = np.nanmin(data[data > -32768]) # handling potential nodata
        max_elev = np.nanmax(data)
        print(f"Elevation Range: {min_elev} to {max_elev}")
        
        # Normalize to 0-65535 for 16-bit PNG
        range_val = max_elev - min_elev
        if range_val == 0: range_val = 1
        
        normalized = ((data - min_elev) / range_val * 65535)
        normalized = np.nan_to_num(normalized, nan=0).astype(np.uint16)
        
        # Create Mask (where data is not nan and not nodata)
        mask_arr = (data > -10000).astype(np.uint8) * 255 # Simple heuristic for valid data
        
        # Save Heightmap
        heightmap_path = DATA_DIR / "dem" / f"{country_name}_heightmap.png"
        Image.fromarray(normalized, mode='I;16').save(heightmap_path)
        
        # Save Mask
        mask_path = DATA_DIR / "dem" / f"{country_name}_mask.png"
        Image.fromarray(mask_arr, mode='L').save(mask_path)
        
        # Metadata
        if country_name == "Greece":
            local_name = "ΕΛΛΗΝΙΚΉ ΔΗΜΟΚΡΑΤÍA"
            english_name = "HELLENIC REPUBLIC" 
        elif country_name == "South Korea":
            local_name = "대한민국"
            english_name = "REPUBLIC OF KOREA"
        else:
            local_name = attributes.get('NAME', country_name)
            english_name = attributes.get('NAME_EN', country_name)
            
        # Calculate center lat for projection correction
        bounds = geometry.bounds
        center_lat = (bounds[1] + bounds[3]) / 2

        metadata = {
            "country_name": country_name,
            "local_name": local_name,
            "english_name": english_name,
            "min_elevation": float(min_elev),
            "max_elevation": float(max_elev),
            "width": src.width,
            "height": src.height,
            "center_lat": center_lat,
            "crs": str(src.crs)
        }
        
        json_path = DATA_DIR / "dem" / "metadata.json"
        with open(json_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        print(f"Exported heightmap to {heightmap_path}")
        print(f"Exported metadata to {json_path}")

def main():
    setup_directories()
    shp_path = download_shapefile()
    geometry, attributes = get_country_geometry(shp_path, COUNTRY_NAME)
    
    # dem_path = download_dem(geometry, COUNTRY_NAME) # Old
    dem_path = download_dem_manual(geometry, COUNTRY_NAME)
    
    clipped_dem = clip_dem(dem_path, geometry, COUNTRY_NAME)
    
    export_for_blender(clipped_dem, geometry, attributes, COUNTRY_NAME)
    
    print("Data preparation finished successfully.")

if __name__ == "__main__":
    main()
