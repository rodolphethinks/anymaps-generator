from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import subprocess
import os
from pathlib import Path
import threading
import time
import sys

app = Flask(__name__)
CORS(app)

CONFIG_PATH = "config.json"
OUTPUT_DIR = Path("output")
PYTHON_EXE = ".\\venv\\Scripts\\python.exe"
# Fallback if venv python not found
if not os.path.exists(PYTHON_EXE):
    PYTHON_EXE = sys.executable
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

# Global state for job tracking
current_job = {
    "status": "idle",  # idle, preparing, rendering, complete, error
    "message": "",
    "current_file": None
}

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        else:
            return jsonify({
                "location_name": "",
                "location_type": "country",
                "parent_country": None,
                "colors": {
                    "low_color": [0.95, 0.98, 1.0, 1.0],
                    "high_color": [0.02, 0.1, 0.5, 1.0]
                }
            })
    
    elif request.method == 'POST':
        data = request.json
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return jsonify({"success": True})

@app.route('/api/generate', methods=['POST'])
def generate_map():
    global current_job
    
    if current_job["status"] in ["preparing", "rendering"]:
        return jsonify({"error": "Job already running"}), 400
    
    data = request.json
    
    # Save config
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    # Start generation in background
    thread = threading.Thread(target=run_generation)
    thread.start()
    
    return jsonify({"success": True, "message": "Generation started"})

def run_process_with_logging(command, stage_name):
    global current_job
    current_job["status"] = stage_name
    
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read stdout line by line
        for line in process.stdout:
            line = line.strip()
            if line:
                current_job["message"] = line
                print(f"[{stage_name}] {line}")
        
        # Determine success
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            current_job["status"] = "error"
            # Prefer stderr if available, otherwise use last message
            error_msg = stderr.strip() if stderr else "Unknown error"
            current_job["message"] = f"{stage_name} failed: {error_msg}"
            print(f"[{stage_name} ERROR] {stderr}")
            return False
            
        return True
        
    except Exception as e:
        current_job["status"] = "error"
        current_job["message"] = f"Error in {stage_name}: {str(e)}"
        print(f"[{stage_name} EXCEPTION] {e}")
        return False

def run_generation():
    global current_job
    
    try:
        # Step 1: Prepare Data
        current_job["message"] = "Starting data preparation..."
        success = run_process_with_logging(
            [PYTHON_EXE, "-u", "prepare_data.py"], 
            "preparing"
        )
        
        if not success:
            return
        
        # Step 2: Render
        current_job["message"] = "Starting Blender render..."
        success = run_process_with_logging(
            [BLENDER_EXE, "--background", "--python", "render_map.py"], 
            "rendering"
        )
        
        if not success:
            return
        
        # Check result
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        location_name = config.get("location_name", "")
        # The render script outputs to OUTPUT_DIR
        output_file = OUTPUT_DIR / f"{location_name}_render.png"
        
        if output_file.exists():
            current_job["status"] = "complete"
            current_job["message"] = "Map generated successfully!"
            current_job["current_file"] = f"{location_name}_render.png"
        else:
            current_job["status"] = "error"
            current_job["message"] = f"Render file not found at {output_file}"
            
    except Exception as e:
        current_job["status"] = "error"
        current_job["message"] = f"CRITICAL ERROR: {str(e)}"
@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(current_job)

@app.route('/api/history', methods=['GET'])
def get_history():
    if not OUTPUT_DIR.exists():
        return jsonify([])
    
    files = []
    for file in OUTPUT_DIR.glob("*_render.png"):
        stat = file.stat()
        files.append({
            "filename": file.name,
            "name": file.stem.replace("_render", ""),
            "size": stat.st_size,
            "modified": stat.st_mtime
        })
    
    # Sort by modified time, newest first
    files.sort(key=lambda x: x["modified"], reverse=True)
    return jsonify(files)

@app.route('/api/image/<filename>', methods=['GET'])
def get_image(filename):
    file_path = OUTPUT_DIR / filename
    if file_path.exists() and file_path.suffix == '.png':
        return send_file(file_path, mimetype='image/png')
    return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
