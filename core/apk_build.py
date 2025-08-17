import subprocess
import os

def build_debug_apk(project_dir, log=lambda x: None):
    try:
        log("Ejecutando 'npx cap sync android'...")
        sync = subprocess.run(["npx", "cap", "sync", "android"], cwd=project_dir, capture_output=True, text=True)
        if sync.returncode != 0:
            log(f"ERROR sincronizando Capacitor: {sync.stderr}")
            return False
        log("Compilando APK debug...")
        android_dir = os.path.join(project_dir, "android")
        gradle = subprocess.run(["gradlew.bat", "assembleDebug"], cwd=android_dir, capture_output=True, text=True)
        if gradle.returncode == 0:
            log("APK compilado con éxito.")
            return True
        else:
            log(f"ERROR compilando APK: {gradle.stderr}")
            return False
    except Exception as e:
        log(f"EXCEPCIÓN en compilación APK: {e}")
        return False
