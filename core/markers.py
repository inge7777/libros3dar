import os
import subprocess
import shutil
import cv2

from .env import get_paths

def verificar_nft_marker_creator(log):
    p = get_paths()
    nft_path = p["NFT_CREATOR"]
    if not nft_path.exists():
        log("ADVERTENCIA: Directorio NFT Marker Creator no encontrado.")
        return False
    main_script = nft_path / "app.js"
    if not main_script.exists():
        log(f"ADVERTENCIA: No se encontró 'app.js' en {nft_path}")
        return False
    try:
        res = subprocess.run(["node", "--version"], cwd=str(nft_path), capture_output=True, text=True, shell=True, check=True)
        log(f"✓ NFT-Marker-Creator Node.js {res.stdout.strip()}")
        return True
    except Exception as e:
        log(f"✗ Error verificando NFT-Marker-Creator: {e}")
        return False

def create_nft(log, image_path, marker_name):
    if not verificar_nft_marker_creator(log):
        return False
    p = get_paths()
    nft_dir = p["NFT_CREATOR"]
    try:
        cmd = ["node", "app.js", "-i", os.path.abspath(image_path)]
        log(f"Ejecutando NFT-Marker-Creator: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(nft_dir), capture_output=True, text=True, shell=True, timeout=180)
        if res.returncode != 0 or "error" in res.stderr.lower():
            log(f"✗ Error NFT: {res.stderr or res.stdout}")
            return False
        out_dir = p["WWW"] / "assets" / "markers"
        out_dir.mkdir(parents=True, exist_ok=True)
        base = os.path.splitext(os.path.basename(image_path))[0]
        count = 0
        for ext in [".fset", ".fset3", ".iset"]:
            src = nft_dir / f"{base}{ext}"
            if src.exists():
                dest = out_dir / f"{marker_name}{ext}"
                shutil.move(str(src), str(dest))
                log(f"✓ Archivo NFT movido: {dest}")
                count += 1
        return count > 0
    except Exception as e:
        log(f"✗ Error crítico generando marcador NFT: {e}")
        return False

def create_patt(log, image_path, patt_path):
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise IOError(f"No se pudo cargar imagen: {image_path}")
        img_resized = cv2.resize(img, (16,16), interpolation=cv2.INTER_AREA)
        patt_content = ""
        for _ in range(3):
            for row in img_resized:
                patt_content += " ".join(f"{val:3d}" for val in row) + "\n"
            patt_content += "\n"
        with open(patt_path, "w", encoding="utf-8") as f:
            f.write(patt_content.strip())
        log(f"✓ Patrón .patt generado para: {os.path.basename(image_path)}")
        return True
    except Exception as e:
        log(f"✗ Error generando .patt: {e}")
        return False
