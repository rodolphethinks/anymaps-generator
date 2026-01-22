
import bpy
import sys

try:
    mat = bpy.data.materials.new(name="TestMat")
    
    # Check propery location
    print(f"mat.displacement_method: {mat.displacement_method}")
    try:
        mat.displacement_method = 'DISPLACEMENT'
        print("Set mat.displacement_method to 'DISPLACEMENT'")
    except Exception as e:
        print(f"Failed to set displacement: {e}")

    # Check object adaptive subdivision
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    
    if hasattr(obj, 'cycles'):
        print("obj.cycles exists")
        print(f"Attributes of obj.cycles: {[d for d in dir(obj.cycles) if 'subd' in d or 'adaptive' in d]}")
    else:
         print("obj.cycles DOES NOT exist")
         
    # Check modifier
    mod = obj.modifiers.new(name="Subd", type='SUBSURF')
    print(f"Attributes of modifier: {[d for d in dir(mod) if 'adaptive' in d]}") 

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
