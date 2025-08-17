from pathlib import Path
import os
import subprocess
import sqlite3

BASE_DIR = Path(r"F:\linux\3d-AR")

def get_paths():
    return {
        "BASE_DIR": BASE_DIR,
        "CAP_TEMPLATE": BASE_DIR/"capacitor-template",
        "PROJECT": BASE_DIR/"capacitor",
        "ANDROID": BASE_DIR/"capacitor"/"android",
        "WWW": BASE_DIR/"capacitor"/"www",
        "PAQUETES": BASE_DIR/"paquetes",
        "OUTPUT_APK": BASE_DIR/"output-apk",
        "LOGS": BASE_DIR/"output-apk"/"logs",
        "GEN": BASE_DIR/"generador",
        "BACKEND_DB": BASE_DIR/"backend"/"activaciones.db",
        "BLENDER_EXE": BASE_DIR/"blender"/"blender-4.5.1-windows-x64"/"blender.exe",
        "NFT_CREATOR": BASE_DIR/"nft-creator",
        "GRADLE_HOME": BASE_DIR/"gradle_cache",
        "JAVA_TMP": BASE_DIR/"temp_java",
        "NODE_GLOBAL": BASE_DIR/"node_global",
        "NODE_CACHE": BASE_DIR/"node_cache",
        "ANDROID_BUILDS": BASE_DIR/"android_builds",
        "TEMP": BASE_DIR/"temp",
        "TMP": BASE_DIR/"temp",
    }

def set_env(p):
    for key in ["GRADLE_HOME","JAVA_TMP","NODE_GLOBAL","NODE_CACHE","ANDROID_BUILDS","TEMP","TMP"]:
        p[key].mkdir(parents=True, exist_ok=True)
    os.environ["GRADLE_USER_HOME"] = str(p["GRADLE_HOME"])
    os.environ["JAVA_OPTS"] = f"-Djava.io.tmpdir={p['JAVA_TMP']}"
    os.environ["TEMP"] = str(p["TEMP"])
    os.environ["TMP"] = str(p["TMP"])
    os.environ["npm_config_prefix"] = str(p["NODE_GLOBAL"])
    os.environ["npm_config_cache"] = str(p["NODE_CACHE"])
    os.environ["ANDROID_BUILD_DIR"] = str(p["ANDROID_BUILDS"])

def validate_env(log):
    ok = True
    NODE_DIR = r"F:\linux\nodejs"
    NODE_EXE = os.path.join(NODE_DIR, "node.exe")

    if not os.path.exists(NODE_EXE):
        log(f"✗ CRÍTICO: No se encontró node.exe en {NODE_DIR}")
        ok = False

    # --- Java Validation ---
    try:
        r_java = subprocess.run("java -version", shell=True, capture_output=True, text=True, check=True)
        log(f"✓ Java: {(r_java.stderr or r_java.stdout).strip().splitlines()[0]}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("✗ Java: No encontrado en PATH.")
        ok = False

    # --- Node/NPM/NPX Validation (Direct Call Method) ---
    log("--- Verificando Node.js (Método de Llamada Directa) ---")

    if ok: # Only try node calls if node.exe was found
        # 1. Node
        try:
            r_node = subprocess.run(f'"{NODE_EXE}" --version', shell=True, capture_output=True, text=True, check=True)
            log(f"✓ node.exe: {r_node.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            log(f"✗ node.exe: No se pudo ejecutar desde {NODE_EXE}. Error: {e}")
            ok = False

        # 2. NPM and NPX
        for tool_name in ["npm", "npx"]:
            cli_js_path = os.path.join(NODE_DIR, 'node_modules', tool_name, 'bin', f'{tool_name}-cli.js')

            if not os.path.exists(cli_js_path):
                log(f"✗ {tool_name}: No se encontró el script JS en: {cli_js_path}")
                ok = False
                continue

            command = [NODE_EXE, cli_js_path, "--version"]
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=True, cwd=NODE_DIR)
                log(f"✓ {tool_name}: {result.stdout.strip()}")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                error_output = e.stderr if hasattr(e, 'stderr') else str(e)
                log(f"✗ {tool_name}: Error en llamada directa. Error: {error_output}")
                ok = False

    # --- Other Environment Validations ---
    p = get_paths()
    if not p["BLENDER_EXE"].exists():
        log(f"✗ Blender no encontrado: {p['BLENDER_EXE']}")
        ok = False
    else:
        log(f"✓ Blender OK")

    if not (p["CAP_TEMPLATE"]/"capacitor.config.json").exists():
        log("✗ capacitor-template inválido (falta capacitor.config.json)")
        ok = False
    else:
        log("✓ Plantilla de Capacitor OK")

    p["BACKEND_DB"].parent.mkdir(parents=True, exist_ok=True)
    try:
        sqlite3.connect(p["BACKEND_DB"]).close()
        log("✓ SQLite OK")
    except Exception as e:
        log(f"✗ SQLite error: {e}")
        ok = False

    # --- Final "Escape Hatch" ---
    if not ok:
        log("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        log("!!! ADVERTENCIA: La validación del entorno falló.")
        log("!!! Se te permitirá continuar, pero algunas funciones")
        log("!!! podrían no operar si las herramientas marcadas")
        log("!!! con (✗) no están realmente disponibles.")
        log("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

    # Always return True to allow the application to start
    return True
