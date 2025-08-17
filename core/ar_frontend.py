import os
import json

def write_frontend(www_dir, models_info, log=lambda x: None, propaganda_url="", explicacion_url=""):
    """
    www_dir: carpeta destino (ej: F:/linux/3d-AR/capacitor/www)
    models_info: lista de dicts [{filename:..., props:{...}}, ...]
    log: función para loguear mensajes
    propaganda_url: URL para el enlace de propaganda
    explicacion_url: URL para el enlace de explicación
    """
    os.makedirs(www_dir, exist_ok=True)
    data_dir = os.path.join(www_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    # model_props.json
    with open(os.path.join(data_dir, "model_props.json"), "w", encoding="utf-8") as f:
        json.dump(models_info, f, indent=2)
    # ar_content.js
    with open(os.path.join(data_dir, "ar_content.js"), "w", encoding="utf-8") as f:
        f.write("const MODELS = " + json.dumps(models_info) + ";")

    # Crear enlaces dinámicamente
    propaganda_link = f'<p><a href="{propaganda_url}" target="_blank" rel="noopener noreferrer">Ver propaganda</a></p>' if propaganda_url else ""
    explicacion_link = f'<p><a href="{explicacion_url}" target="_blank" rel="noopener noreferrer">Ver explicación</a></p>' if explicacion_url else ""

    # index.html básico (puedes ampliar después)
    with open(os.path.join(www_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(f"""
<!DOCTYPE html>
<html>
<head>
<title>AR Preview</title>
<script src="https://cdn.jsdelivr.net/npm/three@0.149.0/build/three.min.js"></script>
<script src="data/ar_content.js"></script>
</head>
<body>
<h2>Visor Web AR</h2>
{propaganda_link}
{explicacion_link}
<hr>
<div id="ar_content">Cargando modelos AR...</div>
<script>
for(let m of MODELS){{
  let d=document.getElementById('ar_content');
  d.innerHTML += "<br>Modelo: "+m.filename;
}}
</script>
</body>
</html>
""")
    log(f"Frontend AR generado en {www_dir}")
