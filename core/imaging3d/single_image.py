import os
import subprocess
from .env import get_paths

def generate_single_image_model(input_img, output_glb, log=lambda x: None):
    """
    Pipeline imagen->3D Single-image (profundidad monocular + mesh displacement).
    Aquí implementarás:
      - Llamada a MiDaS (torch) para obtener mapa de profundidad
      - Invocar Blender con script displacement mesh/export
      - Guardar GLB final en output_glb
    """
    p = get_paths()
    # --- Stub de ejemplo para integración ---
    try:
        # Comando ejemplo call a MiDaS (suponiendo script preparado)
        midas_script = p["GEN"]/"midas_depth.py"
        depth_map = p["GEN"]/"depth_map.png"
        cmd_midas = f'python "{midas_script}" --input "{input_img}" --output "{depth_map}"'
        subprocess.run(cmd_midas, shell=True, check=True)
        log("Mapa de profundidad generado con MiDaS")

        # Llamar blender con script displacement.py con depth_map y textura para generar GLB
        displacement_script = p["GEN"]/ "displacement_mesh.py"
        cmd_blender = [
            str(p["BLENDER_EXE"]), "-b", "-P", str(displacement_script),
            "--", input_img, str(depth_map), output_glb
        ]
        subprocess.run(cmd_blender, check=True)
        log(f"Modelo 3D generado y exportado a {output_glb}")
        return True
    except Exception as e:
        log(f"Error generando modelo single-image: {e}")
        return False
