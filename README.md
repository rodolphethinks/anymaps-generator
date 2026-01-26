# AnyMaps Generator

A Python & Blender pipeline to generate 3D artistic relief maps effectively.

## Features
- **Automated Data Prep**: Downloads shapefiles, DEM (SRTM) data, and prepares heightmaps/masks.
- **Blender Rendering**: Procedurally generates a 3D scene with custom shaders, lighting, and camera setup.
- **Custom Styling**: Produces "Hellenic Republic" style maps with localized text and specific color grading.

## Usage (Web App)

### First Time Setup

1. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Frontend Dependencies**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

### Running the App

1. **Start the Backend** (in one terminal):
   ```bash
   python backend.py
   ```
   Backend runs on `http://localhost:5000`

2. **Start the Frontend** (in another terminal):
   ```bash
   cd frontend
   npm run dev
   ```
   Frontend runs on `http://localhost:3000`

3. **Open your browser** to `http://localhost:3000`

The web app provides:
- Beautiful light beige UI
- Real-time generation status
- View newly generated maps
- Browse history of all generated maps
- Color picker for elevation gradients
- Support for countries and regions worldwide

## Usage (CLI)

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
