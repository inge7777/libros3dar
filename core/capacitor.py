import os
import shutil
import json

from .log import safe_log

def ensure_capacitor_app(template_dir, project_dir, app_id, app_name, log=lambda x: None):
    # Borra proyecto anterior si existe
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)
    shutil.copytree(template_dir, project_dir)
    # Actualiza capacitor.config.json
    config_path = os.path.join(project_dir, "capacitor.config.json")
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    config["appId"] = app_id
    config["appName"] = app_name
    config.setdefault("webDir", "www")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    safe_log(log, f"✓ Proyecto Capacitor listo con appId '{app_id}' y appName '{app_name}'")

def set_gradle_namespace(log, android_dir, package_name):
    build_gradle_path = os.path.join(android_dir, "app", "build.gradle")
    if not os.path.exists(build_gradle_path):
        safe_log(log, f"✗ No se encuentra {build_gradle_path}")
        return False
    with open(build_gradle_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    namespace_set = False
    for line in lines:
        if line.strip().startswith("namespace"):
            new_lines.append(f'namespace "{package_name}"\n')
            namespace_set = True
        else:
            new_lines.append(line)
    if not namespace_set:
        inserted = False
        final_lines = []
        for line in lines:
            final_lines.append(line)
            if "android {" in line and not inserted:
                final_lines.append(f'namespace "{package_name}"\n')
                inserted = True
        new_lines = final_lines
    with open(build_gradle_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    safe_log(log, f"✓ build.gradle actualizado con namespace: {package_name}")
    return True
