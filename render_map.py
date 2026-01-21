
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

# Visual Params
RENDER_SAMPLES = 128

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def setup_render_engine():
    bpy.context.scene.render.engine = 'CYCLES'
    # Fallback attempt for feature set
    try:
        bpy.context.scene.cycles.feature_set = 'EXPERIMENTAL'
    except AttributeError:
        pass # Newer blender might not need this or handles it differently

    bpy.context.scene.cycles.device = 'GPU'
    
    # Attempt to enable GPU
    preferences = bpy.context.preferences
    cycles_preferences = preferences.addons['cycles'].preferences
    cycles_preferences.compute_device_type = 'CUDA' 
    cycles_preferences.get_devices()
    
    bpy.context.scene.cycles.use_denoising = True
    bpy.context.scene.cycles.samples = RENDER_SAMPLES

def create_lighting():
    # Sun: North-West Illumination
    bpy.ops.object.light_add(type='SUN', location=(10, -10, 10))
    sun = bpy.context.active_object
    sun.data.energy = 6.0
    sun.data.angle = math.radians(10) # Soft shadows
    sun.rotation_euler = (math.radians(45), math.radians(0), math.radians(135))

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
    ramp.color_ramp.elements[1].color = (0.8, 0.8, 0.8, 1) # Gray edge
    
    links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], grad.inputs['Vector'])
    links.new(grad.outputs['Color'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    bg_plane.data.materials.append(mat)

def create_map_mesh():
    # Create Plane
    width_blender = 10.0
    height_blender = width_blender / ASPECT_RATIO
    
    print(f"Creating Map Mesh: {width_blender} x {height_blender}")
    
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = "MapMesh"
    obj.scale = (width_blender, height_blender, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Subsurf Modifier
    subsurf = obj.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf.subdivision_type = 'SIMPLE'
    
    # Try Adaptive
    try:
        obj.cycles.use_adaptive_subdivision = True
    except AttributeError:
        print("Warning: Adaptive Subdivision API not found or changed. Using Fixed High Level.")
        subsurf.levels = 9
        subsurf.render_levels = 9
    
    # Material
    mat = bpy.data.materials.new(name="MapMat")
    mat.use_nodes = True
    
    # Enable Displacement
    try:
        mat.cycles.displacement_method = 'DISPLACEMENT'
    except AttributeError:
         # Fallback for newer blender API if changed
         pass
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    # --- NODES ---
    output = nodes.new('ShaderNodeOutputMaterial')
    
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.8 # Matte
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
    
    # Displacement Node
    disp_node = nodes.new('ShaderNodeDisplacement')
    disp_node.inputs['Midlevel'].default_value = 0.0
    disp_node.inputs['Scale'].default_value = 0.35 
    
    links.new(coord.outputs['UV'], tex_elev.inputs['Vector'])
    links.new(tex_elev.outputs['Color'], disp_node.inputs['Height'])
    links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])
    
    # Color Ramp
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'B_SPLINE'
    
    e0 = ramp.color_ramp.elements[0]
    e0.position = 0.0
    e0.color = (0.92, 0.96, 1.0, 1) # White/Ice

    if len(ramp.color_ramp.elements) < 2:
        ramp.color_ramp.elements.new(0.4)
    e1 = ramp.color_ramp.elements[1]
    e1.position = 0.4
    e1.color = (0.2, 0.5, 0.85, 1) # Vibrant Blue
    
    if len(ramp.color_ramp.elements) < 3:
         e2 = ramp.color_ramp.elements.new(1.0)
    else:
         e2 = ramp.color_ramp.elements[2]
         
    e2.position = 1.0
    e2.color = (0.01, 0.02, 0.15, 1) # Deep Navy
    
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
    
    # Mix Factor: Mask (0=Transparent, 1=Solid)
    # 0 -> Input 1, 1 -> Input 2
    links.new(tex_mask.outputs['Color'], mix_shader.inputs[0])
    links.new(trans_shader.outputs['BSDF'], mix_shader.inputs[1])
    links.new(bsdf.outputs['BSDF'], mix_shader.inputs[2])
    
    links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])
    
    obj.data.materials.append(mat)
    
    return obj

def setup_camera(map_obj):
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    cam.location = (0, 0, 15)
    cam.rotation_euler = (0, 0, 0)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 14.0 
    bpy.context.scene.camera = cam

def add_text():
    # Local Name
    bpy.ops.object.text_add(location=(0, -6, 0.5))
    txt_local = bpy.context.active_object
    txt_local.data.body = metadata['local_name']
    txt_local.data.align_x = 'CENTER'
    txt_local.data.size = 1.0
    txt_local.data.extrude = 0.05
    
    # English Name
    bpy.ops.object.text_add(location=(0, -7.2, 0.5))
    txt_en = bpy.context.active_object
    txt_en.data.body = metadata['english_name']
    txt_en.data.align_x = 'CENTER'
    txt_en.data.size = 0.6
    txt_en.data.extrude = 0.05
    
    # Material for Text
    mat = bpy.data.materials.new(name="TextMat")
    mat.use_nodes = True
    bsdf = None
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bsdf = n
            break
    if not bsdf:
        bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')

    bsdf.inputs['Base Color'].default_value = (0.1, 0.1, 0.1, 1)
    
    txt_local.data.materials.append(mat)
    txt_en.data.materials.append(mat)

def render():
    bpy.context.scene.render.filepath = str(OUTPUT_DIR / f"{COUNTRY_NAME}_render.png")
    # Resolution
    bpy.context.scene.render.resolution_x = 2400
    bpy.context.scene.render.resolution_y = 3000
    bpy.context.scene.render.resolution_percentage = 100
    
    print("Rendering...")
    bpy.ops.render.render(write_still=True)
    print(f"Render saved to {bpy.context.scene.render.filepath}")
    
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_DIR / f"{COUNTRY_NAME}_scene.blend"))

def main():
    clear_scene()
    setup_render_engine()
    create_lighting()
    create_background()
    map_obj = create_map_mesh()
    setup_camera(map_obj)
    add_text()
    render()

if __name__ == "__main__":
    main()
