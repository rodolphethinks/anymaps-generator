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

2. **Prepare Data**:
   ```bash
   python prepare_data.py
   ```
   This will download `Greece` data (configurable in script) and output to `data/dem/`.

3. **Render**:
   ```bash
   blender --background --python render_map.py
   ```
   (Ensure `blender` is in your PATH).

## Output
Final renders are saved to `output/`.
