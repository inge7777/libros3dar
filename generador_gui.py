# -*- coding: utf-8 -*-
import os
import shutil
import uuid
import subprocess
import re
import json
import sqlite3
from datetime import datetime
import threading
import time # Importar el módulo time
from tkinter import Tk, Frame, Label, Entry, Button, Listbox, Scrollbar, Text, StringVar, filedialog, messagebox, END, LEFT, RIGHT, BOTH, Y, VERTICAL, NORMAL, DISABLED
from PIL import Image, ImageOps, ImageDraw # Importar ImageOps y ImageDraw
from string import Template # Importar Template para el manejo de plantillas HTML
import unicodedata # Importar unicodedata para limpiar_nombre

# ---------------- RUTAS BASE ----------------
# Directorio base donde se encuentran todos los proyectos y salidas.
# Se establece en el directorio padre de la ubicación del script para que coincida con la estructura del proyecto.
try:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
except NameError:
    # Fallback por si se ejecuta en un entorno donde __file__ no está definido
    BASE_DIR = os.path.abspath(os.path.join(os.getcwd(), '..'))

# Plantilla de proyecto Capacitor
CAPACITOR_TEMPLATE = os.path.join(BASE_DIR, "capacitor-template")
# Directorio de trabajo del proyecto Capacitor (donde se copiará la plantilla y se modificará)
PROJECT_DIR = os.path.join(BASE_DIR, "capacitor")
# Directorio de Android dentro del proyecto Capacitor
ANDROID_DIR = os.path.join(PROJECT_DIR, "android")

# Directorios para paquetes y APKs de salida
PAQUETES_DIR = os.path.join(BASE_DIR, "paquetes")
OUTPUT_APK_DIR = os.path.join(BASE_DIR, "output-apk")
# Directorio para scripts y archivos generados por la GUI
GEN_DIR = os.path.join(BASE_DIR, "generador")
# Rutas a ejecutables externos
BLENDER_PATH = r"D:\amazonlibro\blender 3d\blender.exe"

# Rutas a archivos clave dentro del proyecto Android
ICONO_BASE_DIR = os.path.join(ANDROID_DIR, "app", "src", "main", "res")
ANDROID_MANIFEST = os.path.join(ANDROID_DIR, "app", "src", "main", "AndroidManifest.xml")
WWW_DIR = os.path.join(PROJECT_DIR, "www") # Directorio web del proyecto Capacitor
LOGS_DIR = os.path.join(OUTPUT_APK_DIR, "logs")
STRINGS_XML = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "values", "strings.xml")
# Base de datos para las claves de activación del backend
BACKEND_DB = os.path.join(BASE_DIR, "BACKEND", "activaciones.db")
# Script de PowerShell para la compilación del APK (se mantiene para referencia, aunque ahora se usa Gradle directo)
PS_SCRIPT = os.path.join(GEN_DIR, "generador_apk.ps1")

# Ruta al archivo de plantilla HTML
HTML_TEMPLATE_PATH = os.path.join(GEN_DIR, "index_template.html")


# -------------- FUNCIONES AUXILIARES --------------

def limpiar_nombre(nombre: str) -> str:
    """
    Normaliza un nombre para que sea compatible con nombres de archivos/carpetas
    y paquetes Java/Android, eliminando caracteres problemáticos.
    """
    s = unicodedata.normalize("NFKD", nombre).encode("ASCII", "ignore").decode()
    s = s.replace("ñ", "n").replace("Ñ", "N")
    # Elimina cualquier carácter que no sea alfanumérico o guion bajo
    s = re.sub(r"[^a-zA-Z0-9_]", "", s)
    # Limita la longitud para evitar problemas en sistemas de archivos o Android
    return s[:50]

def safe_log(logbox, msg: str):
    """
    Escribe mensajes en el cuadro de log de la GUI con un timestamp,
    asegurando que el widget esté en un estado editable y visible.
    """
    if logbox and logbox.winfo_exists():
        timestamp = datetime.now().strftime("%H:%M:%S")
        logbox.config(state=NORMAL) # Habilitar edición
        logbox.insert(END, f"[{timestamp}] {msg}\n")
        logbox.see(END) # Desplazarse al final
        logbox.config(state=DISABLED) # Deshabilitar edición, solo lectura

def limpiar_carpetas(logbox, nombre: str):
    """
    Limpiay recrea las carpetas de salida necesarias antes de generar un nuevo paquete.
    Esto incluye la carpeta específica del paquete y la carpeta 'www' del proyecto Capacitor.
    """
    paquete_path = os.path.join(PAQUETES_DIR, nombre)
    www_path = WWW_DIR # WWW_DIR ahora apunta al directorio de trabajo del proyecto Capacitor

    # Limpiar y recrear carpeta del paquete
    if os.path.exists(paquete_path):
        safe_log(logbox, f"Limpiando carpeta existente: {paquete_path}")
        shutil.rmtree(paquete_path)
    os.makedirs(paquete_path)
    safe_log(logbox, f"✓ Carpeta del paquete creada/recreada: {paquete_path}")

    # Limpiar y recrear carpeta www (en el proyecto de trabajo de Capacitor)
    # Esta limpieza es crucial para asegurar que el contenido web sea fresco.
    if os.path.exists(www_path):
        safe_log(logbox, f"Limpiando carpeta existente: {www_path}")
        shutil.rmtree(www_path)
    os.makedirs(www_path)
    safe_log(logbox, f"✓ Carpeta www creada/recreada: {www_path}")

def validar_y_crear_carpetas(logbox):
    """
    Crea las carpetas base necesarias para el funcionamiento de la aplicación
    si no existen.
    """
    carpetas = [
        PAQUETES_DIR, OUTPUT_APK_DIR, LOGS_DIR, GEN_DIR, os.path.dirname(BACKEND_DB),
    ]
    for c in carpetas:
        os.makedirs(c, exist_ok=True)
    safe_log(logbox, "✓ Carpetas base verificadas.")

def verificar_entorno(logbox) -> bool:
    """
    Verifica la existencia y funcionalidad de herramientas externas como Java, Blender, npx,
    y la accesibilidad de la base de datos SQLite y la plantilla de Capacitor.
    """
    ok = True
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True, check=True, encoding="utf-8", shell=True)
        safe_log(logbox, f"✓ Java detectado: {result.stderr.splitlines()[0]}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR: Java no está instalado o no accesible: {e}")
        ok = False
    
    if not os.path.exists(BLENDER_PATH):
        safe_log(logbox, f"✗ ERROR: Blender no encontrado en {BLENDER_PATH}")
        ok = False
    else:
        safe_log(logbox, "✓ Blender encontrado.")

    if not shutil.which("npx"):
        safe_log(logbox, "✗ ERROR: 'npx' no encontrado en el PATH del sistema. (¿Node.js instalado?)")
        ok = False
    else:
        try:
            result = subprocess.run(["npx", "--version"], check=True, capture_output=True, text=True, shell=True)
            safe_log(logbox, f"✓ npx detectado y ejecutable: {result.stdout.strip()}")
        except Exception as e:
            safe_log(logbox, f"✗ ERROR: npx no ejecuta correctamente: {e}")
            ok = False

    if not shutil.which("npm"):
        safe_log(logbox, "✗ ERROR: 'npm' no encontrado en el PATH del sistema. (¿Node.js instalado?)")
        ok = False
    else:
        try:
            result = subprocess.run(["npm", "--version"], check=True, capture_output=True, text=True, shell=True)
            safe_log(logbox, f"✓ npm detectado y ejecutable: {result.stdout.strip()}")
        except Exception as e:
            safe_log(logbox, f"✗ ERROR: npm no ejecuta correctamente: {e}")
            ok = False
    try:
        conn = sqlite3.connect(BACKEND_DB)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activaciones (
                token TEXT PRIMARY KEY,
                device_id TEXT,
                fecha TEXT
            )
        """)
        conn.commit()
        conn.close()
        safe_log(logbox, f"✓ Base de datos SQLite accesible y tabla 'activaciones' verificada en: {BACKEND_DB}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR: No se pudo conectar o verificar la base dea bd Sqlite: {e}")
        ok = False
    # La verificación de capacitor.config.json se hará sobre la plantilla
    config_path = os.path.join(CAPACITOR_TEMPLATE, "capacitor.config.json")
    if not os.path.exists(config_path):
        safe_log(logbox, f"✗ ERROR: No se encontró capacitor.config.json en {config_path}")
        ok = False
    else:
        safe_log(logbox, "✓ capacitor.config.json encontrado.")
    return ok

def insertar_claves_en_backend(claves: list):
    """
    Agrega las claves de activación generadas a la tabla 'activaciones'
    en la base de datos SQLite del backend.
    """
    try:
        conn = sqlite3.connect(BACKEND_DB)
        cursor = conn.cursor()
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for clave in claves:
            cursor.execute("INSERT INTO activaciones (token, device_id, fecha) VALUES (?, ?, ?)",
                          (clave, "", fecha))
        conn.commit()
        conn.close()
    except Exception as e:
        raise Exception(f"Error insertando claves en SQLite: {e}")

def corregir_android_manifest(logbox, nombre_paquete_limpio):
    """
    Corrige AndroidManifest.xml con todos los permisos necesarios para AR y cámara.
    """
    if not os.path.exists(ANDROID_MANIFEST):
        safe_log(logbox, f"Advertencia: AndroidManifest.xml no encontrado en {ANDROID_MANIFEST}")
        return

    safe_log(logbox, f"Corrigiendo AndroidManifest.xml completo para: {nombre_paquete_limpio}")

    # Leer el archivo existente
    with open(ANDROID_MANIFEST, "r", encoding="utf-8") as f:
        content = f.read()

    # Permisos necesarios
    required_permissions = [
        '    <uses-permission android:name="android.permission.CAMERA" />',
        '    <uses-permission android:name="android.permission.RECORD_AUDIO" />',
        '    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />',
        '    <uses-permission android:name="android.permission.INTERNET" />',
        '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />',
        '    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />',
        '    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />',
        '    <uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />'
    ]

    # Hardware features
    hardware_features = [
        '    <uses-feature android:name="android.hardware.camera" android:required="true" />',
        '    <uses-feature android:name="android.hardware.camera.autofocus" />',
        '    <uses-feature android:name="android.hardware.microphone" />'
    ]
    
    # Reconstruir el manifiesto para asegurar la correcta colocación de las etiquetas
    manifest_start = content.find('<manifest')
    if manifest_start == -1:
        safe_log(logbox, "✗ ERROR: No se encontró la etiqueta <manifest> en el archivo.")
        return
        
    manifest_end = content.find('>', manifest_start)
    if manifest_end == -1:
        safe_log(logbox, "✗ ERROR: Etiqueta <manifest> malformada o incompleta.")
        return

    # Extraer la parte antes de la etiqueta de cierre, la etiqueta de aplicación y el resto del contenido
    manifest_tag = content[manifest_start:manifest_end+1]
    rest_of_content = content[manifest_end+1:]
    
    application_start = rest_of_content.find('<application')
    application_end = rest_of_content.find('>', application_start) if application_start != -1 else -1

    new_content_parts = [manifest_tag]
    
    # Añadir permisos y features
    permissions_count = 0
    features_count = 0
    for permission in required_permissions:
        if permission.strip() not in rest_of_content:
            new_content_parts.append('\n' + permission)
            permissions_count += 1
            
    for feature in hardware_features:
        if feature.strip() not in rest_of_content:
            new_content_parts.append('\n' + feature)
            features_count += 1

    if application_start != -1:
        # Reconstruir la etiqueta application para asegurar el networkSecurityConfig
        application_tag = rest_of_content[application_start:application_end+1]
        if 'android:networkSecurityConfig=' not in application_tag:
            application_tag = application_tag.replace('<application', 
                                                    '<application\n        android:networkSecurityConfig="@xml/network_security_config"')
        new_content_parts.append(rest_of_content[:application_start])
        new_content_parts.append(application_tag)
        new_content_parts.append(rest_of_content[application_end+1:])
    else:
        new_content_parts.append(rest_of_content)

    new_content = ''.join(new_content_parts)

    # Por último, reemplazar el tema para evitar el error de SplashScreen
    # Usamos una expresión regular para encontrar y reemplazar el valor de android:theme dentro de la etiqueta <application>
    # Esto es más robusto que un simple reemplazo de texto.
    theme_pattern = re.compile(r'(<application[^>]*android:theme=")([^"]+)(")')
    if theme_pattern.search(new_content):
        # Apuntar al nuevo AppTheme que se creará en styles.xml
        new_content = theme_pattern.sub(r'\1@style/AppTheme\3', new_content)
        safe_log(logbox, "✓ Tema de Android en AndroidManifest.xml cambiado a @style/AppTheme.")
    else:
        safe_log(logbox, "Advertencia: No se encontró el atributo android:theme en la etiqueta <application> para reemplazar.")

    # Corregir el nombre de la actividad principal para evitar ClassNotFoundException
    activity_pattern = re.compile(r'(<activity[^>]*android:name=")([^"]+)(")')
    correct_activity_name = f"com.libros3dar.{nombre_paquete_limpio}.MainActivity"
    if activity_pattern.search(new_content):
        new_content = activity_pattern.sub(fr'\1{correct_activity_name}\3', new_content)
        safe_log(logbox, f"✓ Nombre de la actividad principal corregido a: {correct_activity_name}")
    else:
        safe_log(logbox, "Advertencia: No se encontró el atributo android:name en la etiqueta <activity> para reemplazar.")


    try:
        with open(ANDROID_MANIFEST, "w", encoding="utf-8") as f:
            f.write(new_content)
        safe_log(logbox, f"✓ AndroidManifest.xml corregido con {permissions_count} permisos, {features_count} features y tema actualizado.")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR al corregir AndroidManifest.xml: {e}")
        raise


def generar_styles_xml(logbox):
    """
    Crea un archivo styles.xml limpio para evitar referencias a Theme.SplashScreen.
    """
    styles_path = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "values", "styles.xml")
    styles_content = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Base application theme. -->
    <style name="AppTheme" parent="Theme.AppCompat.DayNight.NoActionBar">
        <!-- Customize your theme here. -->
    </style>
</resources>
"""
    try:
        # Asegurarse de que el directorio exista
        os.makedirs(os.path.dirname(styles_path), exist_ok=True)
        with open(styles_path, "w", encoding="utf-8") as f:
            f.write(styles_content)
        safe_log(logbox, f"✓ Archivo styles.xml limpio generado en: {styles_path}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR al generar styles.xml: {e}")
        raise

def update_strings_xml(logbox, nombre: str):
    """
    Actualiza el archivo strings.xml con el nombre de la aplicación proporcionado.
    Este es el nombre visible en el dispositivo.
    """
    # Asegurarse de que STRINGS_XML apunte al archivo en el proyecto de trabajo
    if not os.path.exists(os.path.dirname(STRINGS_XML)):
        os.makedirs(os.path.dirname(STRINGS_XML), exist_ok=True)
    strings_xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
    <resources>
        <string name="app_name">{nombre}</string>
    </resources>"""
    try:
        with open(STRINGS_XML, "w", encoding="utf-8") as f:
            f.write(strings_xml_content)
        safe_log(logbox, f"✓ strings.xml actualizado con app_name: {nombre}.")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR al actualizar strings.xml: {e}")
        raise

def configurar_webview_camera_completo(logbox, android_dir_arg, nombre_paquete_limpio):
    """
    Genera una MainActivity.java mínima, confiando en Capacitor para manejar los plugins y la configuración del WebView.
    Esto soluciona errores de carga de plugins y de permisos.
    """
    package_name = f"com.libros3dar.{nombre_paquete_limpio}"
    java_base_dir = os.path.join(android_dir_arg, "app", "src", "main", "java")
    target_package_dir_parts = package_name.split('.')
    target_package_full_path = os.path.join(java_base_dir, *target_package_dir_parts)
    main_activity_path = os.path.join(target_package_full_path, "MainActivity.java")

    safe_log(logbox, f"Generando MainActivity.java mínima en: {main_activity_path}")

    # Contenido mínimo estándar para una app de Capacitor.
    # Capacitor se encarga de la inicialización de plugins y del WebView.
    main_activity_content = f"""package {package_name};

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{}}
"""
    try:
        os.makedirs(target_package_full_path, exist_ok=True)
        with open(main_activity_path, "w", encoding="utf-8") as f:
            f.write(main_activity_content)
        safe_log(logbox, f"✓ MainActivity.java mínima generada correctamente.")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR al generar la MainActivity.java mínima: {e}")
        raise


def actualizar_paquete_main_activity(logbox, android_package_name):
    """
    Genera el archivo MainActivity.java con el contenido mínimo y correcto para Capacitor 3+,
    confiando en la carga automática de plugins.
    """
    safe_log(logbox, f"Iniciando generación de MainActivity.java para: {android_package_name}")
    java_base_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "java")

    # Determinar la ruta de destino basada en el nuevo nombre de paquete
    target_package_dir_parts = android_package_name.split('.')
    target_package_full_path = os.path.join(java_base_dir, *target_package_dir_parts)
    target_main_activity_path = os.path.join(target_package_full_path, "MainActivity.java")

    # Contenido mínimo para MainActivity.java en Capacitor 3+
    main_activity_java_content = f"""package {android_package_name};

import com.getcapacitor.BridgeActivity;
import android.os.Bundle;

public class MainActivity extends BridgeActivity {{

    @Override
    public void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        // Capacitor 3+ maneja la carga de plugins automáticamente.
        // No es necesario llamar a `this.init()` con una lista de plugins aquí.
    }}
}}
"""
    try:
        # Asegurarse de que el directorio de destino exista
        os.makedirs(target_package_full_path, exist_ok=True)

        # Escribir el nuevo contenido de MainActivity.java
        with open(target_main_activity_path, "w", encoding="utf-8") as f:
            f.write(main_activity_java_content)
        safe_log(logbox, f"✓ MainActivity.java generado/actualizado en: {target_main_activity_path}")
        time.sleep(0.5)

    except Exception as e:
        safe_log(logbox, f"✗ ERROR al generar/actualizar MainActivity.java: {e}")
        raise

def elimina_foreground_icons(logbox):
    """
    Elimina los archivos de íconos 'foreground' antiguos de las carpetas mipmap.
    Estos son parte de los íconos adaptativos que reemplazaremos.
    """
    # Asegurarse de que ICONO_BASE_DIR apunte al proyecto de trabajo
    carpetas = ["mipmap-mdpi", "mipmap-hdpi", "mipmap-xhdpi", "mipmap-xxhdpi", "mipmap-xxxhdpi"]
    for carpeta in carpetas:
        path = os.path.join(ICONO_BASE_DIR, carpeta, "ic_launcher_foreground.png")
        if os.path.exists(path):
            try:
                os.remove(path)
                safe_log(logbox, f"  - Eliminado: {os.path.basename(path)}")
            except Exception as e:
                safe_log(logbox, f"  - Error eliminando foreground icon {path}: {e}")

def elimina_xml_adaptativos(logbox):
    """
    Elimina los archivos XML de íconos adaptativos antiguos (ic_launcher.xml, ic_launcher_round.xml).
    """
    # Asegurarse de que ICONO_BASE_DIR apunte al proyecto de trabajo
    v26_dir = os.path.join(ICONO_BASE_DIR, "mipmap-anydpi-v26")
    for archivo_xml in ["ic_launcher.xml", "ic_launcher_round.xml"]:
        path = os.path.join(v26_dir, archivo_xml)
        if os.path.exists(path):
            try:
                os.remove(path)
                safe_log(logbox, f"  - Eliminado: {os.path.basename(path)}")
            except Exception as e:
                safe_log(logbox, f"  - Error eliminando xml adaptativo {path}: {e}")

def preparar_proyecto_capacitor(logbox):
    """
    Copia una plantilla limpia de Capacitor al directorio de trabajo del proyecto.
    Esto asegura que cada build comience con una base fresca y sin artefactos anteriores.
    """
    capacitor_dir = PROJECT_DIR # Usamos PROJECT_DIR como el directorio de trabajo
    safe_log(logbox, f"Preparando proyecto Capacitor en: {capacitor_dir}")
    if os.path.exists(capacitor_dir):
        safe_log(logbox, f"Limpiando proyecto Capacitor existente: {capacitor_dir}")
        shutil.rmtree(capacitor_dir) # Elimina la carpeta existente
    shutil.copytree(CAPACITOR_TEMPLATE, capacitor_dir) # Copia la plantilla limpia
    safe_log(logbox, f"✓ Plantilla Capacitor copiada a: {capacitor_dir}")

    # Asegurarse de que las carpetas mipmap existan en el proyecto de trabajo después de la copia
    # Esto es importante para la generación de íconos.
    mipmap_folders = [
        os.path.join(ICONO_BASE_DIR, "mipmap-mdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-hdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-xhdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-xxhdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-xxxhdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-anydpi-v26"),
    ]
    for folder in mipmap_folders:
        os.makedirs(folder, exist_ok=True)
    safe_log(logbox, "✓ Carpetas mipmap en proyecto de trabajo verificadas/creadas.")


def ejecutar_cap_sync(logbox, project_dir_arg):
    """
    Ejecuta 'npx cap sync android' para sincronizar el proyecto web con el proyecto nativo de Android.
    Esto es crucial para que los cambios en capacitor.config.json y la carpeta www se reflejen.
    """
    safe_log(logbox, "Ejecutando 'npx cap sync android'...")
    try:
        # CRÍTICO: Usar shell=True para asegurar que los comandos se encuentren en Windows
        # Usamos cwd para ejecutar el comando en el directorio correcto sin usar os.chdir
        npx_cmd = "npx cap sync android" 
        safe_log(logbox, f"Ejecutando: {npx_cmd} en {project_dir_arg}")
        
        # Ejecutar el comando y capturar la salida
        proc = subprocess.run(npx_cmd, capture_output=True, text=True, encoding="utf-8", check=True, shell=True, cwd=project_dir_arg)
        safe_log(logbox, proc.stdout)
        if proc.stderr:
            safe_log(logbox, f"npx cap sync ERR: {proc.stderr}")
        
        safe_log(logbox, "✓ 'npx cap sync android' completado exitosamente.")
        return True
    except subprocess.CalledProcessError as e:
        safe_log(logbox, f"✗ ERROR en la ejecución de 'npx cap sync android': {e.cmd}")
        safe_log(logbox, f"  STDOUT: {e.stdout}")
        safe_log(logbox, f"  STDERR: {e.stderr}")
        messagebox.showerror("Error de Sincronización Capacitor", f"La sincronización de Capacitor falló. Revisa el log.")
        return False
    except Exception as e:
        safe_log(logbox, f"✗ Error inesperado durante 'npx cap sync android': {e}")
        messagebox.showerror("Error inesperado", f"Ocurrió un error inesperado durante la sincronización: {e}")
        return False

def ejecutar_gradle_build(logbox, project_dir_arg, android_dir_arg):
    """
    Ejecuta los comandos de Gradle directamente desde Python para asegurar que se use
    el build.gradle actualizado y se realice una compilación limpia.
    """
    safe_log(logbox, "Iniciando limpieza y compilación de Gradle directamente...")
    try:
        # Limpiar el proyecto Gradle
        # CRÍTICO: Usar shell=True para asegurar que los comandos se encuentren en Windows
        # Usamos cwd para ejecutar el comando en el directorio correcto sin usar os.chdir
        clean_cmd = "gradlew clean"
        safe_log(logbox, f"Ejecutando: {clean_cmd} en {android_dir_arg}")
        proc_clean = subprocess.run(clean_cmd, capture_output=True, text=True, encoding="utf-8", check=True, shell=True, cwd=android_dir_arg)
        safe_log(logbox, proc_clean.stdout)
        if proc_clean.stderr:
            safe_log(logbox, f"Gradle clean ERR: {proc_clean.stderr}")
        safe_log(logbox, "✓ Gradle clean completado.")

        # Construir el APK de depuración
        build_cmd = "gradlew assembleDebug"
        safe_log(logbox, f"Ejecutando: {build_cmd} en {android_dir_arg}")
        proc_build = subprocess.run(build_cmd, capture_output=True, text=True, encoding="utf-8", check=True, shell=True, cwd=android_dir_arg)
        safe_log(logbox, proc_build.stdout)
        if proc_build.stderr:
            safe_log(logbox, f"Gradle assembleDebug ERR: {proc_build.stderr}")
        safe_log(logbox, "✓ Gradle assembleDebug completado.")

        return True
    except subprocess.CalledProcessError as e:
        safe_log(logbox, f"✗ ERROR en la ejecución de Gradle: {e.cmd}")
        safe_log(logbox, f"  STDOUT: {e.stdout}")
        safe_log(logbox, f"  STDERR: {e.stderr}")
        messagebox.showerror("Error de Gradle", f"La compilación de Gradle falló. Revisa el log para más detalles.")
        return False
    except Exception as e:
        safe_log(logbox, f"✗ Error inesperado durante la ejecución de Gradle: {e}")
        messagebox.showerror("Error inesperado", f"Ocurrió un error inesperado durante la compilación: {e}")
        return False


# ---------------------- CLASE PRINCIPAL GUI ----------------------

class GeneradorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador Libros 3D AR")
        self.root.geometry("1260x900") # Tamaño de la ventana de la GUI
        self.nombre_libro = StringVar()
        self.initial_backend_url = "https://192.168.80.16:5000/activar"
        self.backend_url = StringVar(value=self.initial_backend_url) 
        self.portada_path = StringVar()
        self.propaganda_var = StringVar(value="https://www.youtube.com/shorts/6P7IkbiVGP8")
        self.explicacion_var = StringVar()
        self.cant_claves_var = StringVar(value="100")
        self.pares = [] # Lista para almacenar pares de imagen-modelo
        self.claves = [] # Lista para almacenar las claves generadas
        self._portada_path_full = None # Ruta completa de la portada seleccionada
        self.ps_script_path = PS_SCRIPT # Almacenar PS_SCRIPT como atributo de instancia
        self._init_layout() # Inicializar la interfaz de usuario
        validar_y_crear_carpetas(self.logbox) # Crea carpetas base que no dependen de la estructura de Capacitor
        # Verificar el entorno al inicio
        if not verificar_entorno(self.logbox):
            messagebox.showerror("Error de entorno", "Faltan herramientas necesarias. Revisa el log.")

    def _init_layout(self):
        """Inicializa la disposición de los elementos de la GUI."""
        main = Frame(self.root, padx=10, pady=10)
        main.pack(side=LEFT, fill=BOTH, expand=True)

        col_izq = Frame(main)
        col_izq.pack(side=LEFT, fill=Y, padx=(0, 10))

        Label(col_izq, text="1. Nombre del Paquete *", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 2))
        Entry(col_izq, textvariable=self.nombre_libro, width=40).pack(anchor="w", pady=(0, 8))

        Label(col_izq, text="2. URL Backend activación *", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        Entry(col_izq, textvariable=self.backend_url, width=50).pack(anchor="w", pady=(0, 8))

        Label(col_izq, text="3. Portada para ícono *", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        Button(col_izq, text="Subir Portada", command=self.subir_portada).pack(anchor="w")
        Label(col_izq, textvariable=self.portada_path, fg="blue").pack(anchor="w", pady=(0, 8))

        Label(col_izq, text="4. Cantidad de claves *", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        Entry(col_izq, textvariable=self.cant_claves_var, width=10).pack(anchor="w", pady=(0, 8))

        Label(col_izq, text="5. Link de Propaganda *", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        Entry(col_izq, textvariable=self.propaganda_var, width=50).pack(anchor="w", pady=(0, 8))

        Label(col_izq, text="6. Link de Explicación (opcional)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        Entry(col_izq, textvariable=self.explicacion_var, width=50).pack(anchor="w", pady=(0, 8))

        Label(col_izq, text="7. Contenido (Imágenes y Modelos) *", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        Button(col_izq, text="Agregar Imágenes", command=self.agregar_imagenes).pack(anchor="w", pady=2)
        Button(col_izq, text="Agregar Modelos 3D", command=self.agregar_modelos).pack(anchor="w", pady=2)

        col_der = Frame(main)
        col_der.pack(side=LEFT, fill=Y)

        Label(col_der, text="Archivos emparejados:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.lista = Listbox(col_der, width=66, height=12, selectmode="single")
        self.lista.pack(pady=5)
        Button(col_der, text="Quitar Seleccionado", fg="red", command=self.quitar_seleccionado).pack(anchor="w")

        acciones_frame = Frame(main, pady=20)
        acciones_frame.pack(side=LEFT, fill=Y, padx=(20, 0))

        Label(acciones_frame, text="8. Acciones:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))
        Button(acciones_frame, text="Generar Paquete", bg="#28a745", fg="white",
               command=self.generar_paquete, width=18, height=2).pack(pady=5)
        Button(acciones_frame, text="Generar APK", bg="#007bff", fg="white",
               command=self.generar_apk, width=18, height=2).pack(pady=5)
        Button(acciones_frame, text="Limpiar Formulario", fg="black",
               command=self.limpiar_todo, width=18).pack(pady=20)

        log_frame = Frame(self.root, padx=10, pady=10)
        log_frame.pack(side=RIGHT, fill=BOTH, expand=True)
        Label(log_frame, text="Log de la Aplicación:", font=("Segoe UI", 10, "bold")).pack(anchor='w')
        self.logbox = Text(log_frame, height=38, width=70, bg="#f4f4f4", state=DISABLED, font=("Consolas", 9))
        self.logbox.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Corregido: conectar correctamente el scrollbar al Text widget
        scrollbar = Scrollbar(log_frame, orient=VERTICAL, command=self.logbox.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.logbox.config(yscrollcommand=scrollbar.set)

        self.label_progreso = Label(self.root, text="Listo.", relief="sunken", anchor="w", padx=5)
        self.label_progreso.pack(side="bottom", fill="x")

    def set_progress(self, text, color="black"):
        """Actualiza el texto y color de la barra de progreso en la GUI."""
        self.label_progreso.config(text=text, fg=color)
        self.root.update_idletasks() # Forzar actualización de la GUI

    def subir_portada(self):
        """Permite al usuario seleccionar una imagen de portada para el ícono del APK."""
        archivo = filedialog.askopenfilename(title="Selecciona portada para ícono APK",
                                             filetypes=[("Imágenes", "*.jpg *.jpeg *.png")])
        if archivo:
            self.portada_path.set(os.path.basename(archivo))
            self._portada_path_full = archivo
            safe_log(self.logbox, f"Portada seleccionada: {os.path.basename(archivo)}")

    def agregar_imagenes(self):
        """Permite al usuario agregar múltiples imágenes que se usarán como marcadores AR."""
        archivos = filedialog.askopenfilenames(title="Agregar imágenes marcadores",
                                               filetypes=[("Imágenes", "*.jpg *.jpeg *.png")])
        for archivo in archivos:
            # Usa limpiar_nombre para el nombre base del archivo
            base = limpiar_nombre(os.path.splitext(os.path.basename(archivo))[0])
            self.pares.append({"imagen": archivo, "modelo": None, "base": base})
            safe_log(self.logbox, f"Imagen marcador agregada: {os.path.basename(archivo)}")
        self.actualizar_lista()

    def agregar_modelos(self):
        """Permite al usuario agregar múltiples modelos 3D (GLB/FBX)."""
        archivos = filedialog.askopenfilenames(title="Agregar modelos 3D", filetypes=[("Modelos 3D", "*.glb *.fbx")])
        for archivo in archivos:
            # Usa limpiar_nombre para el nombre base del archivo
            base = limpiar_nombre(os.path.splitext(os.path.basename(archivo))[0])
            agregado = False
            for par in self.pares:
                # Intenta emparejar el modelo con una imagen existente si tienen el mismo nombre base
                if par['base'] == base and not par['modelo']:
                    par['modelo'] = archivo
                    agregado = True
                    break
            if not agregado:
                # Si no se emparejó, añade un nuevo par (modelo sin imagen por ahora)
                self.pares.append({"imagen": None, "modelo": archivo, "base": base})
            safe_log(self.logbox, f"Modelo 3D agregado: {os.path.basename(archivo)}")
        self.actualizar_lista()

    def quitar_seleccionado(self):
        """Elimina el elemento seleccionado de la lista de archivos emparejados."""
        seleccion = self.lista.curselection()
        if not seleccion:
            return
        idx = seleccion[0]
        quitado = self.pares.pop(idx)
        safe_log(self.logbox, f"Elemento quitado: {quitado['base']}")
        self.actualizar_lista()

    def limpiar_todo(self):
        """Reinicia todos los campos del formulario y la lista de archivos."""
        self.pares.clear()
        self.nombre_libro.set("")
        # Corregido: Reiniciar a la URL inicial en lugar de google.com
        self.backend_url.set(self.initial_backend_url)
        self.portada_path.set("")
        self.propaganda_var.set("https://www.youtube.com/shorts/6P7IkbiVGP8")
        self.explicacion_var.set("")
        self.cant_claves_var.set("100")
        self._portada_path_full = None
        self.claves.clear()
    
        self.actualizar_lista()
        self.set_progress("Formulario reiniciado.")
        safe_log(self.logbox, "Formulario reiniciado.")

    def actualizar_lista(self):
        """Actualiza la Listbox en la GUI para mostrar los archivos emparejados."""
        self.lista.delete(0, END) # Limpiar la lista actual
        for par in self.pares:
            img_status = "✓" if par['imagen'] else "✗"
            mod_status = "✓" if par['modelo'] else "✗"
            self.lista.insert(END, f"{par['base']} | Imagen: {img_status} | Modelo: {mod_status}")

    def validar_entrada(self) -> bool:
        """
        Valida que todos los campos obligatorios estén llenos y que los archivos
        seleccionados existan en sus rutas originales.
        """
        # Verificar la portada
        if not self._portada_path_full:
            safe_log(self.logbox, "✗ ERROR: No se ha seleccionado una imagen de portada.")
            return False
        if not os.path.exists(self._portada_path_full):
            safe_log(self.logbox, f"✗ ERROR: El archivo de portada no existe en la ruta: {self._portada_path_full}")
            return False

        # Verificar imágenes y modelos emparejados
        if not self.pares:
            safe_log(self.logbox, "✗ ERROR: No se han agregado imágenes o modelos de contenido.")
            return False

        for i, par in enumerate(self.pares):
            if par['imagen'] and not os.path.exists(par['imagen']):
                safe_log(self.logbox, f"✗ ERROR: La imagen marcador '{os.path.basename(par['imagen'])}' no existe en la ruta: {par['imagen']}")
                return False
            if par['modelo'] and not os.path.exists(par['modelo']):
                safe_log(self.logbox, f"✗ ERROR: El modelo 3D '{os.path.basename(par['modelo'])}' no existe en la ruta: {par['modelo']}")
                return False

        safe_log(self.logbox, "✓ Todos los archivos seleccionados verificados en sus rutas originales.")
        return True


    def generar_paquete(self):
        """
        Genera el paquete de contenido, copia los assets, genera claves de activación
        y crea el archivo index.html principal con la lógica de Realidad Aumentada.
        """
        self.set_progress("Generando paquete...")
        # Limpiar y normalizar el nombre del libro/paquete
        nombre = limpiar_nombre(self.nombre_libro.get().strip())
        # Obtener la URL del backend tal como está en el campo de la GUI
        backend_url = self.backend_url.get().strip()
        
        # --- VALIDACIÓN CRÍTICA DE LA URL DEL BACKEND ---
        
        if not backend_url.startswith("https://"):
            messagebox.showerror("Error de URL", "La URL del Backend de activación DEBE comenzar con 'https://'.")
            self.set_progress("Error: URL no es HTTPS.", "red")
            return False
            
        safe_log(self.logbox, f"DEBUG: URL de backend validada y utilizada en index.html: {backend_url}")
        # --- FIN DE VALIDACIÓN CRÍTICA ---

        try:
            cantidad = int(self.cant_claves_var.get().strip())
            if cantidad <= 0:
                raise ValueError("Cantidad inválida")
        except Exception:
            messagebox.showerror("Error", "Cantidad de claves inválida. Debe ser un número positivo.")
            self.set_progress("Error cantidad claves.", "red")
            return False

        # Validaciones de campos obligatorios
        if not nombre or not backend_url or not self._portada_path_full:
            messagebox.showerror("Error", "Datos obligatorios incompletos (Nombre del Paquete, URL Backend, Portada).")
            self.set_progress("Error datos incompletos.", "red")
            return False

        # Validar que los archivos de entrada existan
        if not self.validar_entrada():
            messagebox.showerror("Error", "Faltan archivos de entrada requeridos o no se encontraron.")
            self.set_progress("Error validando entrada.", "red")
            return False

        # Asegurarse de que haya al menos un par imagen-modelo completo para la funcionalidad AR
        if not any(par['imagen'] and par['modelo'] for par in self.pares):
            messagebox.showerror("Error", "Agrega al menos un par imagen-modelo completo para la Realidad Aumentada.")
            self.set_progress("Error: no hay contenido AR completo.", "red")
            return False

        safe_log(self.logbox, f"Iniciando creación del paquete: {nombre}")
        paquete_dir = os.path.join(PAQUETES_DIR, nombre)

        # Limpiar carpetas antes de generar (esto asegura la creación de paquete_dir y WWW_DIR)
        limpiar_carpetas(self.logbox, nombre)

        try:
            safe_log(self.logbox, "DEBUG: Paso 1 - Copiando y convirtiendo portada.")
            # Copiar y convertir la portada a JPG (si es necesario)
            portada_dest = os.path.join(paquete_dir, "portada.jpg")
            # Corrección: Usar r-string para la ruta literal y evitar SyntaxWarning
            safe_log(self.logbox, f"Intentando copiar portada desde '{self._portada_path_full}' a '{portada_dest}'")
            with Image.open(self._portada_path_full) as img:
                img = img.convert("RGB") # Asegurar formato RGB
                img.save(portada_dest, "JPEG", quality=95) # Guardar como JPEG
            time.sleep(0.1) # Pequeña pausa después de guardar imagen
            if not os.path.exists(portada_dest):
                raise IOError(f"El archivo de imagen {os.path.basename(self._portada_path_full)} no pudo ser guardado en {portada_dest}.")
            safe_log(self.logbox, f"✓ Portada copiada a: {portada_dest}")

            safe_log(self.logbox, "DEBUG: Paso 2 - Copiando imágenes y modelos, generando marcadores HTML.")
            # Copiar imágenes y modelos, generar marcadores para el HTML
            marcadores_data = [] # Lista para almacenar los datos de los marcadores para el HTML
            for par in self.pares:
                if par['imagen'] and par['modelo']:
                    # Copiar imagen marcador
                    img_dest = os.path.join(paquete_dir, f"{par['base']}.jpg")
                    with Image.open(par['imagen']) as img:
                        img = img.convert("RGB")
                        img.save(img_dest, "JPEG", quality=95)
                    time.sleep(0.1) # Pausa después de guardar imagen
                    safe_log(self.logbox, f"✓ Imagen marcador copiada: {par['base']}.jpg")

                    # Copiar o convertir modelo a GLB
                    mod_dst = os.path.join(paquete_dir, f"{par['base']}.glb")
                    ext = os.path.splitext(par['modelo'])[1].lower()
                    if ext == ".glb":
                        shutil.copy2(par['modelo'], mod_dst)
                        time.sleep(0.1) # Pausa después de copiar
                    else:
                        self.convertir_con_blender(par['modelo'], mod_dst)
                        time.sleep(0.1) # Pausa después de convertir
                    
                    if os.path.exists(mod_dst):
                        marcadores_data.append({
                            "imagen": f"{par['base']}.jpg", # Nombre del archivo de imagen en el paquete
                            "modelo": f"{par['base']}.glb"  # Nombre del archivo de modelo en el paquete
                        })
                        safe_log(self.logbox, f"✓ Modelo copiado/convertido: {par['base']}.glb")
                    else:
                        safe_log(self.logbox, f"✗ ERROR: No se generó el modelo {par['base']}.glb")

            safe_log(self.logbox, "DEBUG: Paso 3 - Generando claves y guardándolas en SQLite.")
            # Generar claves y guardarlas en SQLite
            self.claves = [str(uuid.uuid4()).upper().replace("-", "")[:10] for _ in range(cantidad)]
            insertar_claves_en_backend(self.claves)
            claves_file = os.path.join(OUTPUT_APK_DIR, f"{nombre}_claves.txt")
            with open(claves_file, "w", encoding="utf-8") as f:
                f.write("\n".join(self.claves))
            time.sleep(0.1) # Pausa después de guardar claves
            safe_log(self.logbox, f"✓ {cantidad} claves generadas en: {claves_file}")

            safe_log(self.logbox, "DEBUG: Paso 4 - Generando HTML de explicación y marcadores AR.")
            # Generar el contenido HTML para la sección de explicación (si se proporciona)
            explicacion_html = ""
            if self.explicacion_var.get().strip():
                url_exp = self.explicacion_var.get().strip().replace("'", "\\'")
                explicacion_html = f'<button class="boton explicacion" onclick="window.open(\'{url_exp}\', \'_blank\')">💡 Explicación</button>'

            # Generar el contenido HTML para los marcadores AR
            marcadores_ar_html = ""
            for idx, marcador in enumerate(marcadores_data):
                # CORRECCIÓN CLAVE AQUÍ: Eliminar el '$' de las URLs en el f-string de Python.
                # El '$' es para template literals de JavaScript, no para f-strings de Python.
                # Al eliminarlo, Python insertará directamente el valor de la variable.
                marcadores_ar_html += f"""
            <a-marker markerhandler id="marker-{idx}" type="pattern" url="{marcador['imagen']}" preset="custom">
                <a-entity gltf-model="url({marcador['modelo']})" scale="0.3 0.3 0.3"
                          animation="property: rotation; to: 0 360 0; loop: true; dur: 6000;"></a-entity>
            </a-marker>
"""
            safe_log(self.logbox, "DEBUG: Paso 5 - Cargando y sustituyendo plantilla HTML.")
            # --- INICIO DE CAMBIO CRÍTICO: CARGAR HTML DESDE ARCHIVO Y USAR TEMPLATE ---
            # Asegurarse de que el archivo de plantilla HTML exista
            if not os.path.exists(HTML_TEMPLATE_PATH):
                raise FileNotFoundError(f"No se encontró el archivo de plantilla HTML: {HTML_TEMPLATE_PATH}")

            with open(HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
                contenido_html_template = Template(f.read()) # Usar Template

            # Reemplazar marcadores de posición en la plantilla usando safe_substitute
            # Se usa safe_substitute para manejar variables que puedan no estar presentes
            contenido_html = contenido_html_template.safe_substitute(
                APP_NAME=nombre,
                BACKEND_URL=backend_url,
                PROPAGANDA_BUTTON=f'<button class="boton propaganda" onclick="window.open(\'{self.propaganda_var.get().strip()}\', \'_blank\')">📢 Video/Promocional</button>',
                EXPLANATION_BUTTON=explicacion_html,
                AR_MARKERS_HTML=marcadores_ar_html,
                # Añadir variables que puedan estar en index_template.html pero no se generen aquí
                # safe_substitute las dejará intactas si no se proporcionan
                capacitorRetries=3, # Valor por defecto o placeholder
                capacitorTimeout=5000, # Valor por defecto o placeholder
                capacitorVersion="5.0.0" # Valor por defecto o placeholder
            )
            safe_log(self.logbox, "DEBUG: Paso 6 - Escribiendo y copiando index.html a WWW_DIR.")
            # El resto del código para guardar y copiar el HTML permanece igual
            index_path = os.path.join(paquete_dir, "index.html")
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(contenido_html)
            time.sleep(0.1) # Pausa después de guardar index.html
            safe_log(self.logbox, f"✓ index.html generado en: {index_path}")

            # Copiar index.html y assets a la carpeta 'www' del proyecto Capacitor
            www_index_path = os.path.join(WWW_DIR, "index.html")
            shutil.copy2(index_path, www_index_path)
            time.sleep(0.1) # Pausa después de copiar index.html a www
            if not os.path.exists(www_index_path):
                raise FileNotFoundError(f"No se pudo copiar index.html a {www_index_path}")
            safe_log(self.logbox, f"✓ index.html copiado a: {www_index_path}")

            safe_log(self.logbox, "DEBUG: Paso 7 - Copiando marcadores y modelos a www.")
            # Copiar marcadores y modelos a www con sobrescritura
            for par in self.pares:
                if par['imagen'] and par['modelo']:
                    # Copiar imagen a www
                    shutil.copy2(par['imagen'], os.path.join(WWW_DIR, f"{par['base']}.jpg"))
                    time.sleep(0.1) # Pausa después de copiar imagen a www
                    safe_log(self.logbox, f"✓ Marcador copiado a www: {par['base']}.jpg")

                    # Copiar modelo (ya convertido a GLB) a www
                    final_model_path_in_package = os.path.join(paquete_dir, f"{par['base']}.glb")
                    if os.path.exists(final_model_path_in_package):
                        shutil.copy2(final_model_path_in_package, os.path.join(WWW_DIR, f"{par['base']}.glb"))
                        time.sleep(0.1) # Pausa después de copiar modelo a www
                        safe_log(self.logbox, f"✓ Modelo copiado a www: {par['base']}.glb")
                    else:
                        safe_log(self.logbox, f"✗ ERROR: No se encontró el modelo {par['base']}.glb para copiar a www.")

            safe_log(self.logbox, "DEBUG: Paso 8 - Actualizando capacitor.config.json. Se usará un esquema HTTP para evitar problemas de Mixed Content en desarrollo.")
            # Actualizar capacitor.config.json con el nuevo appId y appName
            config_path = os.path.join(PROJECT_DIR, "capacitor.config.json") # Apunta al proyecto de trabajo
            config = {
                "appId": f"com.libros3dar.{nombre}", # Usa el nombre limpio para el appId
                "appName": nombre, # Usa el nombre limpio para el appName
                "webDir": "www",
                "bundledWebRuntime": False,
                "plugins": {
                    "Camera": {"androidCameraPermission": True}
                },
                "server": { # Agregado para el androidScheme
                    "androidScheme": "http", # CAMBIO CRÍTICO: Usar HTTP para evitar problemas de Mixed Content en debug
                    "cleartext": True
                },
                "android": { # AÑADIDO: Para permitir mixed content
                    "allowMixedContent": True
                },
                "cordova": {}
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            time.sleep(0.1) # Pausa después de guardar config
            safe_log(self.logbox, f"✓ capacitor.config.json actualizado con appId: com.libros3dar.{nombre}")

            safe_log(self.logbox, "DEBUG: Paso 9 - Actualizando strings.xml.")
            # Actualizar strings.xml con el nuevo nombre de la aplicación
            update_strings_xml(self.logbox, nombre) # Se pasa logbox aquí
            time.sleep(0.1) # Pausa después de actualizar strings.xml
            safe_log(self.logbox, "DEBUG: Paso 10 - Finalizando generación de paquete.")

            self.set_progress("Paquete generado.", "green")
            return True

        except Exception as e:
            messagebox.showerror("Error al generar paquete", f"Ocurrió un error: {e}")
            self.set_progress("Error generando paquete.", "red")
            safe_log(self.logbox, f"✗ ERROR generando paquete: {e}")
            return False

    def convertir_con_blender(self, origen, destino):
        """
        Convierte archivos 3D (ej. FBX) a formato GLB usando Blender.
        """
        safe_log(self.logbox, f"Convirtiendo {os.path.basename(origen)} a GLB...")
        temp_script = os.path.join(GEN_DIR, "temp_convert.py")
        blender_script = f"""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True) # Inicia Blender con una escena vacía
bpy.ops.import_scene.fbx(filepath=r'{origen}') # Importa el archivo FBX
bpy.ops.export_scene.gltf(filepath=r'{destino}', export_format='GLB', export_apply=True) # Exporta a GLB
"""
        with open(temp_script, "w", encoding="utf-8") as f:
            f.write(blender_script)
        time.sleep(0.1) # Pausa después de escribir script temporal
        try:
            # Ejecuta Blender en modo background con el script Python
            # Se usa shell=True para compatibilidad con rutas de Windows que puedan tener espacios.
            subprocess.run([BLENDER_PATH, "--background", "--python", temp_script],
                             check=True, timeout=300, # Tiempo límite de 5 minutos
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", shell=True)
            time.sleep(0.1) # Pausa después de la ejecución de Blender
            if not os.path.exists(destino) or os.path.getsize(destino) == 0:
                raise RuntimeError(f"Archivo {destino} no fue creado correctamente o está vacío.")
            safe_log(self.logbox, f"✓ Conversión exitosa: {os.path.basename(destino)}")
        except subprocess.TimeoutExpired:
            safe_log(self.logbox, f"✗ ERROR: Tiempo de espera agotado en conversión con Blender para {os.path.basename(origen)}")
            raise # Re-lanzar para que el error sea manejado por el llamador
        except Exception as e:
            # Corregido: Usar self.logbox en lugar de logbox (que no está definido aquí)
            safe_log(self.logbox, f"✗ ERROR en conversión con Blender: {e}")
            raise # Re-lanzar para que el error sea manejado por el llamador
        finally:
            if os.path.exists(temp_script):
                os.remove(temp_script)
                time.sleep(0.1) # Pausa después de eliminar script temporal

    def generar_iconos(self):
        """
        Genera los íconos de la aplicación en diferentes resoluciones
        basados en la imagen de portada y los coloca en las carpetas mipmap.
        También corrige el AndroidManifest.xml y elimina íconos adaptativos antiguos.
        """
        self.set_progress("Generando íconos para el APK...")
        safe_log(self.logbox, "Iniciando generación de íconos...")
        try:
            # Limpiar íconos existentes en mipmap-* del proyecto de trabajo antes de generar nuevos
            safe_log(self.logbox, "Limpiando íconos antiguos en mipmap-* del proyecto de trabajo.")
            mipmap_folders = [f for f in os.listdir(ICONO_BASE_DIR) if f.startswith("mipmap-")]
            for mipmap in mipmap_folders:
                folder_path = os.path.join(ICONO_BASE_DIR, mipmap)
                for file in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path) and file.endswith((".png", ".xml")):
                        try:
                            os.remove(file_path)
                            safe_log(self.logbox, f"  - Eliminado: {os.path.basename(file_path)}")
                        except Exception as e:
                            safe_log(self.logbox, f"  - Error eliminando archivo de ícono {file_path}: {e}")
                        time.sleep(0.05) # Pequeña pausa después de eliminar
            safe_log(self.logbox, "✓ Íconos antiguos en mipmap-* limpiados.")

            # Ruta a la portada que se usará para generar los íconos
            portada_path_for_icons = os.path.join(PAQUETES_DIR, limpiar_nombre(self.nombre_libro.get().strip()), "portada.jpg")
            if not os.path.exists(portada_path_for_icons):
                raise FileNotFoundError(f"No se encontró la portada para generar íconos en: {portada_path_for_icons}")
            
            with Image.open(portada_path_for_icons) as img:
                img = img.convert("RGBA") # Asegurar que la imagen tenga canal alfa para transparencia
                resample_mode = Image.Resampling.LANCZOS # Mejor calidad de redimensionado
                mipmaps = { # Definición de tamaños de íconos para diferentes densidades
                    "mipmap-mdpi": 48,
                    "mipmap-hdpi": 72,
                    "mipmap-xhdpi": 96,
                    "mipmap-xxhdpi": 144,
                    "mipmap-xxxhdpi": 192,
                }
                for d, s in mipmaps.items():
                    dest = os.path.join(ICONO_BASE_DIR, d)
                    os.makedirs(dest, exist_ok=True) # Asegurarse de que la carpeta exista
                    
                    # Generar ícono cuadrado (ic_launcher.png)
                    try:
                        ImageOps.fit(img, (s, s), resample_mode).save(os.path.join(dest, "ic_launcher.png"), "PNG")
                        safe_log(self.logbox, f"  - Generado: {os.path.join(d, 'ic_launcher.png')}")
                    except Exception as e:
                        safe_log(self.logbox, f"  - Error generando ic_launcher.png en {d}: {e}")
                    time.sleep(0.05) # Pausa
                    
                    # Generar ícono redondo (ic_launcher_round.png)
                    try:
                        mask = Image.new("L", (s, s), 0)
                        draw = ImageDraw.Draw(mask)
                        draw.ellipse((0, 0, s, s), fill=255) # Máscara circular
                        imgr = ImageOps.fit(img, (s, s), resample_mode)
                        imgr.putalpha(mask) # Aplicar máscara
                        imgr.save(os.path.join(dest, "ic_launcher_round.png"), "PNG")
                        safe_log(self.logbox, f"  - Generado: {os.path.join(d, 'ic_launcher_round.png')}")
                    except Exception as e:
                        safe_log(self.logbox, f"  - Error generando ic_launcher_round.png en {d}: {e}")
                    time.sleep(0.05) # Pausa
            safe_log(self.logbox, "✓ Íconos generados en todos los mipmap del proyecto de trabajo.")
            
            # Llama a corrige_android_manifest con el nombre del paquete limpio
            nombre_paquete_limpio = limpiar_nombre(self.nombre_libro.get().strip())
            # Ya que corregir_android_manifest ya no retorna la cuenta, no es necesario capturarla.
            corregir_android_manifest(self.logbox, nombre_paquete_limpio)
            time.sleep(0.1) # Pausa
            
            elimina_foreground_icons(self.logbox) # Pasar logbox
            time.sleep(0.1) # Pausa
            elimina_xml_adaptativos(self.logbox) # Pasar logbox
            time.sleep(0.1) # Pausa
            safe_log(self.logbox, "✓ Manifest corregido, foregrounds e XML adaptativos eliminados.")
            return True
        except Exception as e:
            safe_log(self.logbox, f"✗ ERROR CRÍTICO generando íconos: {e}")
            messagebox.showerror("Error iconos", f"No se pudieron generar los iconos.\n{e}")
            return False

    def generar_apk(self):
        """
        Inicia el proceso de generación del APK.
        Coordina la preparación del proyecto Capacitor, la generación de íconos,
        la actualización de configuraciones de Android y la compilación de Gradle.
        """
        # Obtener el nombre limpio del paquete/libro
        nombre = limpiar_nombre(self.nombre_libro.get().strip())
        
        if not nombre:
            messagebox.showerror("Error", "El nombre del paquete está vacío. Por favor, ingresa un nombre.")
            return
        
        # --- REORDENAMIENTO CRÍTICO AQUÍ ---
        # 1. Siempre preparar un proyecto Capacitor limpio primero
        preparar_proyecto_capacitor(self.logbox)
        time.sleep(0.1) # Pausa después de preparar proyecto

        # 2. Luego, generar o regenerar el contenido del paquete web (index.html, assets)
        # Esto asegura que el www_dir del proyecto de trabajo tenga el HTML correcto.
        safe_log(self.logbox, "Generando o regenerando el contenido del paquete web (index.html, assets) para el APK...")
        if not self.generar_paquete(): # Esta llamada ahora siempre pondrá el index.html correcto en WWW_DIR
            return
        # --- FIN REORDENAMIENTO ---

        # --- VALIDACIÓN CRÍTICA DE LA URL DEL BACKEND ---
        backend_url_gui = self.backend_url.get().strip()
        
        if not backend_url_gui.startswith("https://"):
            messagebox.showerror("Error de URL", "La URL del Backend de activación DEBE comenzar con 'https://'.")
            self.set_progress("Error: URL no es HTTPS.", "red")
            return
        # Extraer la IP/dominio de la URL para usarla en network_security_config.xml
        backend_host_match = re.search(r'https?://([^:/]+)', backend_url_gui)
        backend_host = backend_host_match.group(1) if backend_host_match else "localhost" # Fallback

        safe_log(self.logbox, f"DEBUG: URL de backend para network_security_config: {backend_url_gui}")
        # --- FIN DE VALIDACIÓN CRÍTICA ---

        # Sobrescribir styles.xml con una versión limpia para evitar errores de tema
        generar_styles_xml(self.logbox)
        time.sleep(0.1)

        # Usar el host extraído para generar network_security_config
        # CRÍTICO: Se ha modificado para usar cleartextTrafficPermitted
        generar_network_security_config(self.logbox, backend_host)
        time.sleep(0.1)

        # PASO CRÍTICO: Actualizar el paquete en MainActivity.java y su estructura de carpetas
        try:
            # El nombre del paquete Android será com.libros3dar.nombre_limpio
            nombre_paquete_limpio = limpiar_nombre(self.nombre_libro.get().strip())
            # AHORA SE LLAMA LA NUEVA FUNCIÓN PARA HABILITAR JAVASCRIPT
            configurar_webview_camera_completo(self.logbox, ANDROID_DIR, nombre_paquete_limpio)
        except Exception as e:
            self.set_progress("Fallo al actualizar MainActivity.java.", "red")
            messagebox.showerror("Error", f"No se pudo actualizar MainActivity.java: {e}")
            return

        # PASO CRÍTICO: Aplicar el build.gradle corregido automáticamente
        try:
            aplicar_build_gradle_corregido(self.logbox, nombre) # Pasamos el nombre limpio del paquete
        except Exception as e:
            self.set_progress("Fallo al aplicar build.gradle corregido.", "red")
            messagebox.showerror("Error", f"No se pudo aplicar el build.gradle corregido: {e}")
            return

        # Generar íconos *después* de que la plantilla haya sido copiada y el manifest corregido
        if not self.generar_iconos():
            self.set_progress("Fallo iconos", "red")
            return
        
        self.set_progress(f"Iniciando compilación del APK para '{nombre}'...")
        # Iniciar la compilación en un hilo separado para no congelar la GUI
        threading.Thread(target=self.build_flow_thread, args=(nombre, PROJECT_DIR, ANDROID_DIR), daemon=True).start()

    def build_flow_thread(self, nombre, project_dir_arg, android_dir_arg):
        """
        Hilo principal que coordina la instalación de plugins, la sincronización de Capacitor y la compilación de Gradle.
        """
        self.set_progress(f"Sincronizando Capacitor y compilando APK para '{nombre}'...")
        safe_log(self.logbox, "======== INICIANDO FLUJO DE BUILD DE APK (SYNC + GRADLE) ========")

        try:
            # Paso 0: Asegurar que el plugin @capacitor/camera esté añadido
            safe_log(self.logbox, "Verificando e instalando plugin @capacitor/camera...")
            try:
                # Instalar el plugin con npm, ejecutando en el directorio del proyecto
                npm_install_cmd = "npm install @capacitor/camera"
                safe_log(self.logbox, f"Ejecutando: {npm_install_cmd} en {project_dir_arg}")
                proc_npm_install = subprocess.run(npm_install_cmd, capture_output=True, text=True, encoding="utf-8", check=False, shell=True, cwd=project_dir_arg)
                safe_log(self.logbox, proc_npm_install.stdout)
                if proc_npm_install.stderr:
                    safe_log(self.logbox, f"npm install ERR: {proc_npm_install.stderr}")
                
                if proc_npm_install.returncode != 0 and \
                   "already installed" not in proc_npm_install.stderr.lower() and \
                   "already installed" not in proc_npm_install.stdout.lower():
                    raise subprocess.CalledProcessError(proc_npm_install.returncode, npm_install_cmd, proc_npm_install.stdout, proc_npm_install.stderr)
                
                safe_log(self.logbox, "✓ Plugin @capacitor/camera instalado via npm.")
                
            except subprocess.CalledProcessError as e:
                safe_log(self.logbox, f"✗ ERROR al instalar plugin @capacitor/camera con npm: {e.cmd}")
                safe_log(self.logbox, f"  STDOUT: {e.stdout}")
                safe_log(self.logbox, f"  STDERR: {e.stderr}")
                messagebox.showerror("Error de Plugin Capacitor", f"No se pudo instalar el plugin de la cámara con npm. Revisa el log.")
                return
            except Exception as e:
                safe_log(self.logbox, f"✗ Error inesperado al instalar plugin @capacitor/camera: {e}")
                messagebox.showerror("Error inesperado", f"Ocurrió un error inesperado al instalar el plugin: {e}")
                return

            # Paso 1: Ejecutar npx cap sync android
            if not ejecutar_cap_sync(self.logbox, project_dir_arg):
                self.set_progress("✗ Sincronización Capacitor fallida.", "red")
                safe_log(self.logbox, "======== BUILD APK FALLIDO (SYNC) ========")
                return
            
            # AÑADIDO: Pequeño retraso para dar tiempo a que los cambios del sync se asienten
            time.sleep(5) # Espera 5 segundos

            # Paso 2: Ejecutar la compilación de Gradle
            if not ejecutar_gradle_build(self.logbox, project_dir_arg, android_dir_arg):
                self.set_progress("✗ Build de Gradle fallido.", "red")
                safe_log(self.logbox, "======== BUILD APK FALLIDO (GRADLE) ========")
                return

            # Verificar si el APK se generó
            apk_output_dir = os.path.join(android_dir_arg, "app", "build", "outputs", "apk", "debug")
            apk_file = None
            for root, _, files in os.walk(apk_output_dir):
                for file in files:
                    if file.endswith("-debug.apk"):
                        apk_file = os.path.join(root, file)
                        break
                if apk_file:
                    break

            if apk_file and os.path.exists(apk_file):
                final_apk_dest_dir = os.path.join(OUTPUT_APK_DIR, nombre)
                os.makedirs(final_apk_dest_dir, exist_ok=True)
                final_apk_path = os.path.join(final_apk_dest_dir, f"{nombre}-debug.apk")
                shutil.copy2(apk_file, final_apk_path)
                safe_log(self.logbox, f"✓ APK copiado a: {final_apk_path}")

                claves_str = "\n".join(self.claves) if self.claves else ""
                if claves_str:
                    clave_file = os.path.join(final_apk_dest_dir, "claves-activacion.txt")
                    with open(clave_file, "w", encoding="utf-8") as f:
                        f.write(claves_str)
                    safe_log(self.logbox, f"✓ Archivo de claves creado en {clave_file}")

                self.set_progress("✅ ¡APK generado y build terminado!", "green")
                safe_log(self.logbox, "======== BUILD APK COMPLETADO ========")
                messagebox.showinfo(
                    "Éxito",
                    f"APK generado y copiado a: {final_apk_path}\nEl APK está firmado (debug) y listo para instalar.\nPara firma release, configura tu keystore en build.gradle o usa Android Studio."
                )
            else:
                self.set_progress("✗ APK no encontrado después del build.", "red")
                safe_log(self.logbox, "✗ ERROR: Archivo APK no encontrado después de la compilación de Gradle.")
                messagebox.showerror("Error de compilación", "El archivo APK no se generó. Revisa el log para más detalles.")
        except Exception as e:
            safe_log(self.logbox, f"✗ Error crítico en build_flow_thread: {e}")
            messagebox.showerror("Error crítico", f"Ocurrió un error inesperado durante la compilación del APK: {e}")


    def build_thread(self, nombre, portada_path, ps_script_arg, project_dir_arg, android_dir_arg):
        """
        [DEPRECADO] Hilo para ejecutar el script de PowerShell para la compilación del APK.
        Ahora se prefiere 'build_flow_thread'.
        """
        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR)
        if not os.path.exists(os.path.join(project_dir_arg, "www", "index.html")):
            safe_log(self.logbox, "✗ ERROR: Falta index.html en www. Aborta build.")
            messagebox.showerror("Build abortado", "Falta index.html en www. El build no puede continuar.")
            return
        if not os.path.exists(ps_script_arg):
            # Corregido: usar ps_script_arg en el mensaje de error
            safe_log(self.logbox, f"✗ ERROR: Falta script {ps_script_arg}")
            messagebox.showerror("Build abortado", f"El script PowerShell no existe: {ps_script_arg}")
            return
        if not os.path.exists(portada_path):
            safe_log(self.logbox, f"✗ ERROR: Falta portada en {portada_path}")
            messagebox.showerror("Build abortado", f"La portada no existe: {portada_path}")
            return
        safe_log(self.logbox, "======== INICIANDO BUILD DE APK (VIA POWERSHELL) ========")
        claves_str = ",".join(self.claves) if self.claves else ""
        env = os.environ.copy()
        
        cmd = [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ps_script_arg,
            "-PaqueteNombre",
            nombre,
            "-PortadaPath",
            portada_path, # Corregido: Faltaba el argumento de la ruta de la portada
            "-Claves",
            claves_str,
            "-ProjectDir",
            project_dir_arg,
            "-AndroidDir",
            android_dir_arg
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=env, shell=True)
            for line in iter(proc.stdout.readline, ""):
                safe_log(self.logbox, line.rstrip())
                self.set_progress(f"Compilando: {line.strip()[:100]}")
            proc.wait()
            if proc.returncode == 0:
                self.set_progress("✅ ¡APK generado y build terminado!", "green")
                safe_log(self.logbox, "======== BUILD APK COMPLETADO ========")
                apk_output_dir = os.path.join(OUTPUT_APK_DIR, nombre)
                apk_path = os.path.join(apk_output_dir, f"{nombre}-debug.apk")
                mensaje = "APK generado. "
                if os.path.exists(apk_path):
                    mensaje += f"Archivo: {apk_path}"
                else:
                    mensaje += f"Revisa: {OUTPUT_APK_DIR}"
                messagebox.showinfo(
                    "Éxito",
                    mensaje + "\nEl APK está firmado (debug) y listo para instalar.\nPara firma release, configura tu keystore en generador_apk.ps1.",
                )
            else:
                logs = [os.path.join(LOGS_DIR, f) for f in os.listdir(LOGS_DIR) if f.endswith(".log")]
                logs.sort(key=os.path.getmtime, reverse=True)
                mensaje_logs = f"\nVerifica el log: {logs[0]}" if logs else ""
                self.set_progress(f"✗ Build falló. Error: {proc.returncode}", "red")
                safe_log(self.logbox, f"======== BUILD APK FALLIDO ({proc.returncode}) ========{mensaje_logs}")
                messagebox.showerror("Compilación", "La compilación falló. Revisa el log." + mensaje_logs)
        except Exception as e:
            safe_log(self.logbox, f"✗ Error en build: {e}")
            messagebox.showerror("Error crítico", str(e))

def generar_network_security_config(logbox, backend_host):
    """
    Genera el archivo network_security_config.xml para permitir tráfico no seguro desde el host del backend.
    """
    network_security_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "xml")
    network_security_file = os.path.join(network_security_dir, "network_security_config.xml")
    
    os.makedirs(network_security_dir, exist_ok=True)
    
    network_security_content = f"""<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">{backend_host}</domain>
    </domain-config>
</network-security-config>
"""
    try:
        with open(network_security_file, "w", encoding="utf-8") as f:
            f.write(network_security_content)
        safe_log(logbox, f"✓ network_security_config.xml generado en: {network_security_file}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR al generar network_security_config.xml: {e}")
        raise

def aplicar_build_gradle_corregido(logbox, nombre):
    """
    Modifica inteligentemente el build.gradle del proyecto Android para asegurar compatibilidad,
    preservando las dependencias de los plugins de Capacitor.
    - Asegura que el namespace esté presente.
    - Fija las versiones de SDK a las requeridas.
    """
    build_gradle_path = os.path.join(ANDROID_DIR, "app", "build.gradle")
    application_id = f"com.libros3dar.{nombre}"
    
    safe_log(logbox, f"Modificando inteligentemente build.gradle en: {build_gradle_path}")

    try:
        with open(build_gradle_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Asegurar compileSdkVersion
        content = re.sub(r'compileSdkVersion \d+', 'compileSdkVersion 35', content)
        safe_log(logbox, "  - compileSdkVersion fijado a 35.")

        # 2. Asegurar targetSdkVersion
        content = re.sub(r'targetSdkVersion \d+', 'targetSdkVersion 35', content)
        safe_log(logbox, "  - targetSdkVersion fijado a 35.")
        
        # 3. Asegurar minSdkVersion
        content = re.sub(r'minSdkVersion \d+', 'minSdkVersion 23', content)
        safe_log(logbox, "  - minSdkVersion fijado a 23.")

        # 4. Asegurar el namespace. Esto es CRÍTICO para builds recientes.
        # Si 'namespace' no está, lo insertamos. Si está, lo actualizamos.
        if 'namespace' not in content:
            # Insertar el namespace justo después de 'android {'
            content = re.sub(r'(android\s*{)', rf'\1\n    namespace "{application_id}"', content, 1)
            safe_log(logbox, f"  - Namespace insertado: {application_id}")
        else:
            # Si ya existe, lo reemplazamos para asegurar que es el correcto
            content = re.sub(r'namespace\s+".+"', f'namespace "{application_id}"', content)
            safe_log(logbox, f"  - Namespace actualizado a: {application_id}")

        with open(build_gradle_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        safe_log(logbox, f"✓ build.gradle modificado exitosamente.")

    except FileNotFoundError:
        safe_log(logbox, f"✗ ERROR: No se encontró el archivo build.gradle en {build_gradle_path}. Esto no debería pasar si la sincronización de Capacitor fue exitosa.")
        raise
    except Exception as e:
        safe_log(logbox, f"✗ ERROR al modificar build.gradle: {e}")
        raise

if __name__ == "__main__":
    root = Tk()
    app = GeneradorGUI(root)
    root.mainloop()
