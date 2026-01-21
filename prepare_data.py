
import os
import zipfile
import requests
import geopandas as gpd
import elevation
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
# Point to the existing cache in the sibling directory to avoid re-downloading massively
EXISTING_CACHE_DIR = Path("../map_render/data/dem/srtm_cache").resolve()
SHAPEFILE_URL = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip"
COUNTRY_NAME = "Greece"

def setup_directories():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "shapefiles").mkdir(exist_ok=True)
    (DATA_DIR / "dem").mkdir(exist_ok=True)
    
    if not EXISTING_CACHE_DIR.exists():
        print(f"Warning: Cache dir {EXISTING_CACHE_DIR} not found. Downloads might happen.")

def download_shapefile():
    target_zip = DATA_DIR / "shapefiles" / "ne_10m_admin_0_countries.zip"
    target_shp = DATA_DIR / "shapefiles" / "ne_10m_admin_0_countries.shp"
    
    if target_shp.exists():
        print(f"Shapefile already exists at {target_shp}")
        return target_shp

    print(f"Downloading shapefile from {SHAPEFILE_URL}...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(SHAPEFILE_URL, headers=headers, stream=True)
        if response.status_code == 200:
            with open(target_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)
            print("Download complete. Extracting...")
            with zipfile.ZipFile(target_zip, 'r') as zip_ref:
                zip_ref.extractall(DATA_DIR / "shapefiles")
            print("Extraction complete.")
        else:
             print(f"Failed to download shapefile: {response.status_code}")
             # Fallback if download fails? Not implemented.
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

def download_dem(geometry, country_name):
    # Get bounds
    bounds = geometry.bounds # minx, miny, maxx, maxy
    print(f"Bounds: {bounds}")
    
    output_dem = DATA_DIR / "dem" / f"{country_name}_raw.tif"
    
    if output_dem.exists():
        print(f"Raw DEM already exists: {output_dem}")
        return output_dem

    min_lon = int(math.floor(bounds[0]))
    max_lon = int(math.ceil(bounds[2]))
    min_lat = int(math.floor(bounds[1]))
    max_lat = int(math.ceil(bounds[3]))
    
    tiles_to_merge = []
    
    print(f"Looking for tiles covering: Lon {min_lon}-{max_lon}, Lat {min_lat}-{max_lat} in {EXISTING_CACHE_DIR}")
    
    # Try to find tiles in cache
    if EXISTING_CACHE_DIR.exists():
        for lat in range(min_lat, max_lat):
            for lon in range(min_lon, max_lon):
                # Format: N34E019.hgt
                ns = 'N' if lat >= 0 else 'S'
                ew = 'E' if lon >= 0 else 'W'
                filename = f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}.hgt"
                
                file_path = EXISTING_CACHE_DIR / filename
                if not file_path.exists():
                     # checking for .tif just in case
                    filename_tif = f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}.tif"
                    file_path_tif = EXISTING_CACHE_DIR / filename_tif
                    if file_path_tif.exists():
                         file_path = file_path_tif

                if file_path.exists():
                    print(f"Found tile: {file_path.name}")
                    tiles_to_merge.append(file_path)
                else:
                    print(f"Missing tile: {filename} (might be ocean or outside coverage)")

    if not tiles_to_merge:
        print("No tiles found in cache. Attempting 'elevation' download...")
        # Fallback to elevation tool download
        margin = 0.1
        minx, miny, maxx, maxy = bounds
        os.environ['ELEVATION_CACHE_DIR'] = str(DATA_DIR / "dem" / "cache")
        try:
            elevation.clip(bounds=(minx-margin, miny-margin, maxx+margin, maxy+margin), output=str(output_dem), product='SRTM3')
            return output_dem
        except Exception as e:
            raise Exception("Failed to download DEM via elevation tool and no cache found.") from e

    print(f"Merging {len(tiles_to_merge)} tiles...")
    
    src_files_to_close = []
    try:
        datasets = []
        for p in tiles_to_merge:
            src = rasterio.open(p)
            src_files_to_close.append(src)
            datasets.append(src)

        mosaic, out_trans = merge(datasets)
        
        out_meta = datasets[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans,
            "crs": datasets[0].crs
        })

        with rasterio.open(output_dem, "w", **out_meta) as dest:
            dest.write(mosaic)
            
        print(f"Merged DEM saved to {output_dem}")
        
    finally:
        for src in src_files_to_close:
            src.close()

    return output_dem

def clip_dem(dem_path, geometry, country_name):
    print("Clipping DEM to country boundaries...")
    with rasterio.open(dem_path) as src:
        out_image, out_transform = mask(src, [geometry], crop=True)
        out_meta = src.meta
    
    out_meta.update({"driver": "GTiff",
                     "height": out_image.shape[1],
                     "width": out_image.shape[2],
                     "transform": out_transform})
    
    output_clipped = DATA_DIR / "dem" / f"{country_name}_clipped.tif"
    
    with rasterio.open(output_clipped, "w", **out_meta) as dest:
        dest.write(out_image)
        
    print(f"Clipped DEM saved to {output_clipped}")
    return output_clipped

def export_for_blender(dem_path, geometry, attributes, country_name):
    print("Exporting data for Blender...")
    
    with rasterio.open(dem_path) as src:
        data = src.read(1)
        # Handle nodata
        if src.nodata is not None:
             data = np.where(data == src.nodata, np.nan, data)
        
        # Min/Max for scaling
        min_elev = np.nanmin(data)
        max_elev = np.nanmax(data)
        print(f"Elevation range: {min_elev} to {max_elev}")
        
        if np.isnan(min_elev) or np.isnan(max_elev):
             print("Warning: elevation data is all NaN?")
             min_elev = 0
             max_elev = 1

        # Normalize to 0-65535 for 16-bit PNG
        range_val = max_elev - min_elev
        if range_val == 0: range_val = 1
        
        normalized = ((data - min_elev) / range_val * 65535)
        normalized = np.nan_to_num(normalized, nan=0).astype(np.uint16)
        
        # Create Mask (where data is not nan)
        mask_arr = (~np.isnan(data)).astype(np.uint8) * 255
        
        # Save Heightmap
        heightmap_path = DATA_DIR / "dem" / f"{country_name}_heightmap.png"
        Image.fromarray(normalized, mode='I;16').save(heightmap_path)
        
        # Save Mask
        mask_path = DATA_DIR / "dem" / f"{country_name}_mask.png"
        Image.fromarray(mask_arr, mode='L').save(mask_path)
        
        # Metadata
        # Manual override for Greece for this test
        if country_name == "Greece":
            local_name = "ΕΛΛΗΝΙΚΉ ΔΗΜΟΚΡΑΤÍA"
            english_name = "HELLENIC REPUBLIC" # Style from the image
        else:
            local_name = attributes.get('NAME', country_name)
            english_name = attributes.get('NAME_EN', country_name)

        metadata = {
            "country_name": country_name,
            "local_name": local_name,
            "english_name": english_name,
            "min_elevation": float(min_elev),
            "max_elevation": float(max_elev),
            "width": src.width,
            "height": src.height,
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
    
    dem_path = download_dem(geometry, COUNTRY_NAME)
    clipped_dem = clip_dem(dem_path, geometry, COUNTRY_NAME)
    
    export_for_blender(clipped_dem, geometry, attributes, COUNTRY_NAME)
    
    print("Data preparation finished successfully.")

if __name__ == "__main__":
    main()
