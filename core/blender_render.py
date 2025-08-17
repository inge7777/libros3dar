import os
import uuid
import subprocess
from .env import get_paths

def render_still(glb_path, out_png, props, res=(3840,2160), samples=256, log=lambda x:None):
    p = get_paths()
    p["GEN"].mkdir(exist_ok=True, parents=True)
    glb_abs = os.path.abspath(glb_path)
    out_abs = os.path.abspath(out_png)
    col = props.get("color", "")
    rot = float(props.get("rotateY") or 0.0)
    scl = float(props.get("scale") or 1.0)
    tm = float(props.get("targetMeters") or 0.0)
    tex = props.get("texture", "") or ""
    script_path = p["GEN"]/f"render_{uuid.uuid4().hex}.py"
    script_code = f'''
import bpy, math
from mathutils import Vector
bpy.ops.wm.read_homefile(use_empty=True)
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = {int(samples)}
bpy.context.scene.render.resolution_x = {int(res[0])}
bpy.context.scene.render.resolution_y = {int(res[1])}
bpy.context.scene.render.film_transparent = True
bpy.ops.object.light_add(type='AREA', location=(2,2,2))
bpy.data.lights[-1].energy = 1500
bpy.ops.object.light_add(type='AREA', location=(-2,-2,3))
bpy.data.lights[-1].energy = 1200
bpy.ops.object.camera_add(location=(0,-3,1.5), rotation=(math.radians(70),0,0))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.import_scene.gltf(filepath=r"{glb_abs}")
model = [o for o in bpy.context.selected_objects if o.type not in ('CAMERA','LIGHT')]
if model:
    bpy.ops.object.select_all(action='DESELECT')
    for o in model:
        o.select_set(True)
    bpy.ops.object.join()
    model = bpy.context.active_object
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    maxd = max(model.dimensions) if model.dimensions else 1.0
    final_scale = ({tm}/maxd if {tm}>0 else 1.0/maxd) * max({scl}, 0.01)
    model.scale = (final_scale,)*3
    model.rotation_euler[2] = math.radians({rot})
    bbox = [Vector(b) for b in model.bound_box]
    center = sum(bbox, Vector())/8.0
    model.location -= center
    hexcol = "{col}"
    if hexcol and len(hexcol)==7 and hexcol=='#':
        r,g,b = (int(hexcol[i:i+2],16)/255.0 for i in (1,3,5))
        for o in model.children_recursive:
            if getattr(o,'type','')=='MESH':
                for s in o.material_slots:
                    if s.material and s.material.node_tree:
                        nt = s.material.node_tree
                        for n in nt.nodes:
                            if n.type=='BSDF_PRINCIPLED':
                                n.inputs['Base Color'].default_value = (r,g,b,1.0)
    tex = r"{tex}"
    if tex and os.path.exists(tex):
        img = bpy.data.images.load(tex)
        for o in model.children_recursive:
            if getattr(o,'type','')=='MESH':
                for s in o.material_slots:
                    if s.material and s.material.node_tree:
                        nt = s.material.node_tree
                        bsdf = next((n for n in nt.nodes if n.type=='BSDF_PRINCIPLED'), None)
                        if bsdf:
                            texnode = nt.nodes.new('ShaderNodeTexImage')
                            texnode.image = img
                            nt.links.new(texnode.outputs['Color'], bsdf.inputs['Base Color'])
bpy.context.scene.render.filepath = r"{out_abs}"
bpy.ops.render.render(write_still=True)
'''
    script_path.write_text(script_code, encoding="utf-8")
    result = subprocess.run([str(p["BLENDER_EXE"]), "-b", "-P", str(script_path)], capture_output=True, text=True)
    if result.returncode == 0:
        log("Render OK")
    else:
        log(f"Render ERROR: {(result.stderr or result.stdout)[-600:]}")
    try:
        script_path.unlink()
    except:
        pass
    return result.returncode == 0
