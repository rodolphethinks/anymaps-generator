
import bpy
import json
import os
import math
from pathlib import Path

# Setup Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
DATA_DIR = SCRIPT_DIR / "data" / "dem"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

METADATA_PATH = DATA_DIR / "metadata.json"

# Load Metadata
with open(METADATA_PATH, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

COUNTRY_NAME = metadata['country_name']
HEIGHTMAP_PATH = DATA_DIR / f"{COUNTRY_NAME}_heightmap.png"
MASK_PATH = DATA_DIR / f"{COUNTRY_NAME}_mask.png"

# Parameters
ASPECT_RATIO = metadata['width'] / metadata['height']
MIN_ELEV = metadata['min_elevation'] 
MAX_ELEV = metadata['max_elevation'] 
ELEV_RANGE = MAX_ELEV - MIN_ELEV
CENTER_LAT = metadata.get('center_lat', 0)

# Lat correction: EPSG:4326 is stretched horizontally as we go away from equator.
# We need to shrink X by cos(lat) to make it look "Metric" / Upright.
LAT_CORRECTION = 1 / math.cos(math.radians(CENTER_LAT)) if math.cos(math.radians(CENTER_LAT)) != 0 else 1.0

# Visual Params
RENDER_SAMPLES = 128

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def setup_render_engine():
    bpy.context.scene.render.engine = 'CYCLES'
    try:
        bpy.context.scene.cycles.feature_set = 'EXPERIMENTAL'
    except AttributeError:
        pass

    bpy.context.scene.cycles.device = 'GPU'
    
    preferences = bpy.context.preferences
    cycles_preferences = preferences.addons['cycles'].preferences
    cycles_preferences.compute_device_type = 'CUDA' 
    cycles_preferences.get_devices()
    
    bpy.context.scene.cycles.use_denoising = True
    bpy.context.scene.cycles.samples = RENDER_SAMPLES

def create_lighting():
    # Sun: Very high Z for close shadows
    # High Z (25) means rays are almost vertical -> short shadows
    bpy.ops.object.light_add(type='SUN', location=(3, -3, 25))
    sun = bpy.context.active_object
    sun.data.energy = 5.0
    sun.data.angle = math.radians(2) # Very sharp shadows
    sun.rotation_euler = (math.radians(20), math.radians(5), math.radians(145))

def create_background():
    # White-gray circular gradient
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0, 0, -2))
    bg_plane = bpy.context.active_object
    bg_plane.name = "Background"
    
    # Material
    mat = bpy.data.materials.new(name="BackgroundMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 1.0
    bsdf.inputs['Specular IOR Level'].default_value = 0.0
    
    # Gradient
    grad = nodes.new('ShaderNodeTexGradient')
    grad.gradient_type = 'SPHERICAL'
    
    # Mapping
    mapping = nodes.new('ShaderNodeMapping')
    coord = nodes.new('ShaderNodeTexCoord')
    # Center the spherical gradient
    mapping.inputs['Location'].default_value = (-0.5, -0.5, 0)
    
    # Color Ramp
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (1, 1, 1, 1) # White center
    ramp.color_ramp.elements[1].color = (0.85, 0.85, 0.85, 1) # Subtle Gray edge
    
    links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], grad.inputs['Vector'])
    links.new(grad.outputs['Color'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    bg_plane.data.materials.append(mat)

def create_map_mesh():
    # Center map slightly UP (Y=2) to leave space below for text
    # Dimension calculations
    width_blender = 10.0
    height_blender = width_blender / ASPECT_RATIO
    scale_x = width_blender / LAT_CORRECTION
    
    print(f"Creating Map Mesh: {scale_x} x {height_blender}")
    
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 1.5, 0))
    obj = bpy.context.active_object
    obj.name = "MapMesh"
    
    obj.scale = (scale_x, height_blender, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Subsurf Modifier
    subsurf = obj.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf.subdivision_type = 'SIMPLE'
    
    try:
        obj.cycles.use_adaptive_subdivision = True
    except AttributeError:
        subsurf.levels = 9
        subsurf.render_levels = 9
    
    # Material
    mat = bpy.data.materials.new(name="MapMat")
    mat.use_nodes = True
    
    try:
        mat.cycles.displacement_method = 'DISPLACEMENT'
    except AttributeError:
         pass
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    # --- NODES ---
    output = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.8 
    bsdf.inputs['Specular IOR Level'].default_value = 0.0
    
    coord = nodes.new('ShaderNodeTexCoord')
    
    # Heightmap
    if str(HEIGHTMAP_PATH) not in bpy.data.images:
        img = bpy.data.images.load(str(HEIGHTMAP_PATH))
    else:
        img = bpy.data.images[str(HEIGHTMAP_PATH)]
    img.colorspace_settings.name = 'Non-Color'
    
    tex_elev = nodes.new('ShaderNodeTexImage')
    tex_elev.image = img
    tex_elev.interpolation = 'Cubic' 
    tex_elev.extension = 'EXTEND'
    
    # Displacement
    disp_node = nodes.new('ShaderNodeDisplacement')
    disp_node.inputs['Midlevel'].default_value = 0.0
    # EXAGGERATED Elevation
    disp_node.inputs['Scale'].default_value = 1.5 
    
    links.new(coord.outputs['UV'], tex_elev.inputs['Vector'])
    links.new(tex_elev.outputs['Color'], disp_node.inputs['Height'])
    links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])
    
    # Color Ramp
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'B_SPLINE'
    
    # 0: White
    e0 = ramp.color_ramp.elements[0]
    e0.position = 0.0
    e0.color = (0.95, 0.98, 1.0, 1)

    # 1: Electric Blue (High Saturation)
    if len(ramp.color_ramp.elements) < 2:
        ramp.color_ramp.elements.new(0.4)
    e1 = ramp.color_ramp.elements[1]
    e1.position = 0.42
    e1.color = (0.0, 0.2, 1.0, 1) # Saturated
    
    # 2: Deep Navy
    if len(ramp.color_ramp.elements) < 3:
         e2 = ramp.color_ramp.elements.new(1.0)
    else:
         e2 = ramp.color_ramp.elements[2]
         
    e2.position = 1.0
    e2.color = (0.0, 0.005, 0.15, 1) 
    
    links.new(tex_elev.outputs['Color'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    
    # Masking
    if str(MASK_PATH) not in bpy.data.images:
        mask_img = bpy.data.images.load(str(MASK_PATH))
    else:
        mask_img = bpy.data.images[str(MASK_PATH)]
    mask_img.colorspace_settings.name = 'Non-Color'
        
    tex_mask = nodes.new('ShaderNodeTexImage')
    tex_mask.image = mask_img
    tex_mask.interpolation = 'Closest' 
    
    mix_shader = nodes.new('ShaderNodeMixShader')
    trans_shader = nodes.new('ShaderNodeBsdfTransparent')
    links.new(coord.outputs['UV'], tex_mask.inputs['Vector'])
    links.new(tex_mask.outputs['Color'], mix_shader.inputs['Fac'])
    links.new(trans_shader.outputs['BSDF'], mix_shader.inputs[1])
    links.new(bsdf.outputs['BSDF'], mix_shader.inputs[2])
    
    links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])
    
    obj.data.materials.append(mat)
    return obj

def setup_camera():
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    # Camera centered slightly above origin to frame map+text
    cam.location = (0, 0.5, 15)
    cam.rotation_euler = (0, 0, 0)
    cam.data.type = 'ORTHO'
    # Widen frame
    cam.data.ortho_scale = 16.0 
    bpy.context.scene.camera = cam

def add_text():
    # Try to load Arial
    font_path = "C:\\Windows\\Fonts\\arial.ttf"
    fnt = None
    if os.path.exists(font_path):
        try:
            fnt = bpy.data.fonts.load(font_path)
        except:
            pass

    # Layout: Map is at Y=1.5, Height~8 -> Bottom ~ -2.5.
    # Place text in the empty space below.
    
    # Local Name
    bpy.ops.object.text_add(location=(0, -4.0, 0.5))
    txt_local = bpy.context.active_object
    if fnt: txt_local.data.font = fnt
    txt_local.data.body = metadata['local_name']
    txt_local.data.align_x = 'CENTER'
    txt_local.data.size = 1.2
    txt_local.data.extrude = 0.05
    txt_local.data.character_spacing = 1.1
    
    # English Name
    bpy.ops.object.text_add(location=(0, -5.5, 0.5))
    txt_en = bpy.context.active_object
    if fnt: txt_en.data.font = fnt
    txt_en.data.body = metadata['english_name']
    txt_en.data.align_x = 'CENTER'
    txt_en.data.size = 0.7
    txt_en.data.extrude = 0.05
    txt_en.data.character_spacing = 2.5 # Wide spacing for style
    
    # Material
    mat = bpy.data.materials.new(name="TextMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if not bsdf:
        bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1) # Dark Gray
    
    txt_local.data.materials.append(mat)
    txt_en.data.materials.append(mat)

def render():
    bpy.context.scene.render.filepath = str(OUTPUT_DIR / f"{COUNTRY_NAME}_render.png")
    bpy.context.scene.render.resolution_x = 2400
    bpy.context.scene.render.resolution_y = 3000
    
    print("Rendering...")
    bpy.ops.render.render(write_still=True)
    print(f"Render saved to {bpy.context.scene.render.filepath}")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_DIR / f"{COUNTRY_NAME}_scene.blend"))

def main():
    clear_scene()
    setup_render_engine()
    create_lighting()
    create_background()
    create_map_mesh() # creates object at Y=1.5
    setup_camera()
    add_text()
    render()

if __name__ == "__main__":
    main()
