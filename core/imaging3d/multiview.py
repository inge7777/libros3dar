import os
import subprocess
from .env import get_paths

def generate_multiview_model(images_dir, output_glb, log=lambda x: None, colmap_bin="colmap"):
    """
    Pipeline Multi-View:
     - Ejecuta SfM y MVS con COLMAP a partir de varias fotos,
     - Malla de densidad,
     - Limpieza y exportación como GLB (usando Blender headless).
    """
    p = get_paths()
    workspace = os.path.join(p["GEN"], "colmap_out")
    if os.path.exists(workspace):
        import shutil
        shutil.rmtree(workspace)
    os.makedirs(workspace, exist_ok=True)
    # 1. Features y matchings
    log("Iniciando pipeline COLMAP...")
    cmd_feat = [
        colmap_bin, "feature_extractor",
        "--database_path", os.path.join(workspace, "database.db"),
        "--image_path", images_dir
    ]
    cmd_match = [
        colmap_bin, "exhaustive_matcher",
        "--database_path", os.path.join(workspace, "database.db")
    ]
    cmd_mapper = [
        colmap_bin, "mapper",
        "--database_path", os.path.join(workspace, "database.db"),
        "--image_path", images_dir,
        "--output_path", os.path.join(workspace, "sparse")
    ]
    cmd_img_reg = [
        colmap_bin, "image_undistorter",
        "--image_path", images_dir,
        "--input_path", os.path.join(workspace, "sparse", "0"),
        "--output_path", os.path.join(workspace, "dense"),
        "--output_type", "COLMAP"
    ]
    cmd_dense = [
        colmap_bin, "patch_match_stereo",
        "--workspace_path", os.path.join(workspace, "dense")
    ]
    cmd_fusion = [
        colmap_bin, "stereo_fusion",
        "--workspace_path", os.path.join(workspace, "dense"),
        "--output_path", os.path.join(workspace, "dense", "fused.ply")
    ]
    cmds = [cmd_feat, cmd_match, cmd_mapper, cmd_img_reg, cmd_dense, cmd_fusion]
    for cmd in cmds:
        log(" ".join(cmd))
        ret = subprocess.run(cmd, capture_output=True, text=True)
        if ret.returncode != 0:
            log(f"❌ Error: {ret.stderr[:400]}")
            return False
    log("COLMAP completado, malla en fused.ply")
    # 2. Malla a GLB usando Blender headless
    fused_ply = os.path.join(workspace, "dense", "fused.ply")
    if not os.path.exists(fused_ply):
        log("❌ fused.ply no generado, abortando.")
        return False
    blender_script = f'''
import bpy
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_mesh.ply(filepath=r"{fused_ply}")
obj = bpy.context.selected_objects[0]
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
bpy.ops.export_scene.gltf(filepath=r"{os.path.abspath(output_glb)}", export_format='GLB', export_yup=True)
'''
    script_path = os.path.join(workspace, "export_glb.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(blender_script)
    ret = subprocess.run([
        str(p["BLENDER_EXE"]),
        "-b", "-P", script_path
    ], capture_output=True, text=True)
    log("Export a GLB OK." if ret.returncode == 0 else f"Blender/GLB error: {ret.stderr[:600]}")
    return ret.returncode == 0
