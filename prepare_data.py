import os
import zipfile
import requests
import geopandas as gpd
# import elevation 
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.enums import Resampling
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
COUNTRIES_SHP_URL = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip"
REGIONS_SHP_URL = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"

CONFIG_PATH = Path("config.json")
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

LOCATION_NAME = config.get("location_name", "South Korea")
LOCATION_TYPE = config.get("location_type", "country") # country or region
PARENT_COUNTRY = config.get("parent_country", None) # Optional, mainly for regions
COLORS = config.get("colors", {})

def setup_directories():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "shapefiles").mkdir(exist_ok=True)
    (DATA_DIR / "dem").mkdir(exist_ok=True)
    EXISTING_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def download_shapefile(url, filename):
    target_zip = DATA_DIR / "shapefiles" / f"{filename}.zip"
    target_shp = DATA_DIR / "shapefiles" / f"{filename}.shp"
    
    if target_shp.exists():
        print(f"Shapefile {filename} already exists.")
        return target_shp

    print(f"Downloading shapefile from {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, stream=True)
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

def get_geometry(location_name, location_type, parent_country=None):
    print(f"Finding geometry for {location_name} ({location_type})...")
    
    if location_type == 'region':
        shp_path = download_shapefile(REGIONS_SHP_URL, "ne_10m_admin_1_states_provinces")
        gdf = gpd.read_file(shp_path)
        
        # Filter by name
        # Try 'name' first, then 'woe_name', then 'gn_name'
        matches = gdf[gdf['name'] == location_name]
        if matches.empty:
            matches = gdf[gdf['woe_name'] == location_name]
        if matches.empty:
            matches = gdf[gdf['gn_name'] == location_name]
            
        # If parent country is specified, filter by it
        if not matches.empty and parent_country:
             matches = matches[matches['admin'] == parent_country]
             
        if matches.empty:
             raise ValueError(f"Region '{location_name}' not found.")
             
        result = matches.iloc[0]
        return result.geometry, result
        
    else:
        shp_path = download_shapefile(COUNTRIES_SHP_URL, "ne_10m_admin_0_countries")
        gdf = gpd.read_file(shp_path)
        
        country = gdf[gdf['ADMIN'] == location_name]
        if country.empty:
            country = gdf[gdf['NAME'] == location_name]
        
        if country.empty:
            raise ValueError(f"Country '{location_name}' not found.")
        
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

def export_for_blender(dem_path, geometry, attributes, name):
    print("Exporting for Blender...")
    
    MAX_DIM = 16384 # Limit texture size to 16k to prevent Memory Errors
    
    with rasterio.open(dem_path) as src:
        # Check dimensions
        h, w = src.height, src.width
        
        # Determine strict downsampling scale
        scale = 1.0
        if max(h, w) > MAX_DIM:
            scale = MAX_DIM / max(h, w)
            new_h = int(h * scale)
            new_w = int(w * scale)
            print(f"Image too large ({w}x{h}), downsampling to ({new_w}x{new_h})...")
            
            data = src.read(
                1,
                out_shape=(new_h, new_w),
                resampling=Resampling.bilinear
            )
        else:
            data = src.read(1)

        # Stats
        valid_mask = data > -10000
        if np.any(valid_mask):
            min_elev = np.nanmin(data[valid_mask])
            max_elev = np.nanmax(data[valid_mask])
        else:
            min_elev = 0
            max_elev = 1
            
        print(f"Elevation Range: {min_elev} to {max_elev}")
        
        # Clamp data to min_elev to avoid negative wrap-around for NoData
        data_clamped = np.where(valid_mask, data, min_elev) 
        
        # Normalize to 0-65535 for 16-bit PNG
        range_val = max_elev - min_elev
        if range_val == 0: range_val = 1
        
        normalized = ((data_clamped - min_elev) / range_val * 65535)
        normalized = np.nan_to_num(normalized, nan=0).astype(np.uint16)
        
        # Create Mask (where data is not nan and not nodata)
        mask_arr = (valid_mask).astype(np.uint8) * 255
        
        # Save Heightmap
        heightmap_path = DATA_DIR / "dem" / f"{name}_heightmap.png"
        Image.fromarray(normalized, mode='I;16').save(heightmap_path)
        
        # Save Mask
        mask_path = DATA_DIR / "dem" / f"{name}_mask.png"
        Image.fromarray(mask_arr, mode='L').save(mask_path)
        
        # Get actual dimensions for metadata
        out_height, out_width = data.shape

        # Metadata Logic
        local_name = attributes.get('name_local', name)
        if hasattr(local_name, 'isnull') and local_name.isnull(): # check if pandas series/value is null
             local_name = name
        elif not local_name:
             local_name = name
             
        # Fallback table
        if name == "Greece":
            local_name = "ΕΛΛΗΝΙΚΉ ΔΗΜΟΚΡΑΤÍA"
        elif name == "South Korea":
            local_name = "대한민국"
        elif name == "Algeria":
            local_name = "الجمهورية الجزائرية"
        elif LOCATION_TYPE == 'region':
             # Try to get local name from region attributes if available
             pass

        english_name = attributes.get('name_en', name)
        if not english_name:
             english_name = attributes.get('name', name)

        if name == "South Korea": 
             english_name = "REPUBLIC OF KOREA"
        elif name == "Algeria":
             english_name = "PEOPLE'S DEMOCRATIC REPUBLIC OF ALGERIA"
        
        # Sanitize text
        if isinstance(local_name, str): local_name = local_name.strip()
        if isinstance(english_name, str): english_name = english_name.upper().strip()

        # Calculate center lat for projection correction
        bounds = geometry.bounds
        center_lat = (bounds[1] + bounds[3]) / 2

        metadata = {
            "country_name": name,
            "local_name": local_name,
            "english_name": english_name,
            "min_elevation": float(min_elev),
            "max_elevation": float(max_elev),
            "width": out_width,
            "height": out_height,
            "center_lat": center_lat,
            "crs": str(src.crs),
            "colors": COLORS 
        }
        
        json_path = DATA_DIR / "dem" / "metadata.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
            
        print(f"Exported heightmap to {heightmap_path}")
        print(f"Exported metadata to {json_path}")

def main():
    setup_directories()
    
    geometry, attributes = get_geometry(LOCATION_NAME, LOCATION_TYPE, PARENT_COUNTRY)
    
    dem_path = download_dem_manual(geometry, LOCATION_NAME)
    
    clipped_dem = clip_dem(dem_path, geometry, LOCATION_NAME)
    
    export_for_blender(clipped_dem, geometry, attributes, LOCATION_NAME)
    
    print("Data preparation finished successfully.")

if __name__ == "__main__":
    main()
