# AnyMaps Generator

A Python & Blender pipeline to generate 3D artistic relief maps effectively.

## Features
- **Automated Data Prep**: Downloads shapefiles, DEM (SRTM) data, and prepares heightmaps/masks.
- **Blender Rendering**: Procedurally generates a 3D scene with custom shaders, lighting, and camera setup.
- **Custom Styling**: Produces "Hellenic Republic" style maps with localized text and specific color grading.

## Usage

1. **Setup Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate # or venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure**:
   Edit `config.json` to choose your location and style:
   ```json
   {
       "location_name": "Hérault",
       "location_type": "region", 
       "parent_country": "France",
       "colors": {
           "low_color": [0.95, 0.98, 1.0, 1.0], 
           "high_color": [0.02, 0.1, 0.5, 1.0]
       }
   }
   ```
   *   `location_type`: "country" or "region" (e.g. US States, French Departments).
   *   `colors`: RBGA values for the gradient (Low to High).

3. **Prepare Data**:
   ```bash
   python prepare_data.py
   ```
   This will download necessary data handling the location specified in `config.json`.

4. **Render**:
   ```bash
   blender --background --python render_map.py
   ```
   (Ensure `blender` is in your PATH).

## Output
Final renders are saved to `output/`.
