import subprocess
import os
import uuid
from .env import get_paths

def fbx_to_glb(fbx_path, out_glb, log):
    p = get_paths()
    p["GEN"].mkdir(exist_ok=True, parents=True)
    script_path = p["GEN"]/f"fbx2glb_{uuid.uuid4().hex}.py"
    script_code = f"""
import bpy
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"{os.path.abspath(fbx_path)}")
for o in bpy.context.scene.objects:
    if o.type != 'CAMERA' and o.type != 'LIGHT':
        o.select_set(True)
    else:
        o.select_set(False)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
bpy.ops.export_scene.gltf(filepath=r"{os.path.abspath(out_glb)}", export_format='GLB', export_yup=True)
"""
    script_path.write_text(script_code, encoding="utf-8")
    cmd = [str(p["BLENDER_EXE"]), "-b", "-P", str(script_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        log("FBX→GLB OK")
    else:
        log(f"FBX→GLB ERROR: {(proc.stderr or proc.stdout)[-400:]}")
    try:
        script_path.unlink()
    except:
        pass
    return proc.returncode == 0
