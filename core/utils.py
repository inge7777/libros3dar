import unicodedata
import re

def limpiar_nombre(nombre: str) -> str:
    """
    Normaliza un nombre para que sea compatible con nombres de archivos/carpetas
    y paquetes Java/Android, eliminando caracteres problemáticos y convirtiendo a minúsculas.
    """
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode()
    # Elimina cualquier carácter que no sea alfanumérico o guion bajo
    s = re.sub(r'[^a-zA-Z0-9_]', '', s)
    # Retorna en minúsculas y limitado en longitud
    return s.lower()[:50]
