import re

# Ejemplo de contrato esperado:
# {"scale": float, "color": "#RRGGBB" or "", "rotateY": float, "targetMeters": float or None, "texture": str}

def parse_command_fallback(command):
    """
    Parse simple para buscar propiedades básicas en un string.
    """
    props = {
        "scale": 1.0,
        "color": "",
        "rotateY": 0.0,
        "targetMeters": None,
        "texture": ""
    }
    # Buscar escala (scale)
    m = re.search(r"scale\s*=\s*([\d\.]+)", command, re.I)
    if m:
        try:
            props["scale"] = float(m.group(1))
        except:
            pass
    # Buscar color (#RRGGBB o nombre simple)
    m = re.search(r"color\s*=\s*('#?[a-zA-Z0-9]+')", command, re.I)
    if m:
        color = m.group(1).strip("'\"")
        if re.match(r"#([0-9a-fA-F]{6})", color):
            props["color"] = color
        else:
            props["color"] = ""
    # Buscar rotación en Y (grados)
    m = re.search(r"rotateY\s*=\s*(-?[\d\.]+)", command, re.I)
    if m:
        try:
            props["rotateY"] = float(m.group(1))
        except:
            pass
    # Buscar distancia targetMeters
    m = re.search(r"targetMeters\s*=\s*([\d\.]+)", command, re.I)
    if m:
        try:
            props["targetMeters"] = float(m.group(1))
        except:
            props["targetMeters"] = None
    # Buscar textura
    m = re.search(r'texture\s*=\s*["\']([^"\']+)["\']', command, re.I)
    if m:
        props["texture"] = m.group(1)
    return props

def try_load_phi2(command):
    """
    Intenta usar Phi-2 para extraer props; si falla, fallback parse_command_fallback
    """
    try:
        # Aquí pondrías tu integración real
        props_llm = {}  # resultado del LLM
        if props_llm:
            return props_llm
    except Exception:
        pass
    return parse_command_fallback(command)
