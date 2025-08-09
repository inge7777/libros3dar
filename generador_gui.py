# -*- coding: utf-8 -*-
import os
import shutil
import sys
import uuid
import subprocess
import re
import json
import sqlite3
from datetime import datetime
import threading
import time # Importar el módulo time
import requests # Importar requests
from tkinter import Tk, Frame, Label, Entry, Button, Listbox, Scrollbar, Text, StringVar, filedialog, messagebox, END, LEFT, RIGHT, BOTH, Y, VERTICAL, NORMAL, DISABLED, Toplevel
from PIL import Image, ImageOps, ImageDraw # Importar ImageOps y ImageDraw
from string import Template # Importar Template para el manejo de plantillas HTML

# --- Dependencias con autoinstalación ---
try:
    from flask import Flask, send_from_directory, jsonify
    from pyngrok import ngrok
    import cv2
    import numpy as np
    import psutil # Para verificar el espacio en disco
except ImportError:
    print("Dependencias críticas no encontradas. Intentando instalar...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Flask", "pyngrok", "opencv-python", "numpy", "Pillow", "psutil"])
    from flask import Flask, send_from_directory, jsonify
    from pyngrok import ngrok
    import cv2
    import numpy as np
    import psutil

# ---------------- RUTAS BASE ----------------
# Directorio base donde se encuentran todos los proyectos y salidas
BASE_DIR = r"D:\libros3dar2"
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
BACKEND_DB = os.path.join(BASE_DIR, "backend", "activaciones.db")
# Script de PowerShell para la compilación del APK (se mantiene para referencia, aunque ahora se usa Gradle directo)
PS_SCRIPT = os.path.join(GEN_DIR, "generador_apk.ps1")

import unicodedata # Importar unicodedata para limpiar_nombre

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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                device_id TEXT,
                fecha_creacion TEXT NOT NULL,
                usado INTEGER DEFAULT 0,
                fecha_uso TEXT
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

def insertar_claves_en_backend(logbox, claves: list):
    """
    Agrega las claves de activación generadas a la tabla 'activaciones'.
    """
    safe_log(logbox, f"Iniciando inserción de {len(claves)} claves en la base de datos...")
    try:
        conn = sqlite3.connect(BACKEND_DB)
        cursor = conn.cursor()
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inserted_count = 0
        for clave in claves:
            # Inserta solo el token y la fecha. El device_id se asociará en el primer uso.
            try:
                cursor.execute("INSERT INTO activaciones (token, fecha_creacion) VALUES (?, ?)",
                              (clave, fecha))
                inserted_count += 1
            except sqlite3.IntegrityError:
                safe_log(logbox, f"  - La clave {clave} ya existe en la base de datos. Se omite.")
        conn.commit()
        conn.close()
        safe_log(logbox, f"✓ Inserción completada. {inserted_count} nuevas claves añadidas a la base de datos.")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR CRÍTICO insertando claves en SQLite: {e}")
        raise Exception(f"Error insertando claves en SQLite: {e}")

def corregir_android_manifest(logbox, nombre_paquete_limpio):
    '''
    Reconstruye AndroidManifest.xml con todos los permisos y features necesarios para AR.
    '''
    if not os.path.exists(os.path.dirname(ANDROID_MANIFEST)):
        safe_log(logbox, f"Error: El directorio para AndroidManifest.xml no existe. Abortando.")
        return

    manifest_content = f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Permisos necesarios para AR y WebRTC -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="28" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="28" />

    <!-- Features de hardware -->
    <uses-feature android:name="android.hardware.camera" android:required="true" />
    <uses-feature android:name="android.hardware.camera.autofocus" android:required="false" />
    <uses-feature android:name="android.hardware.camera.front" android:required="false" />
    <uses-feature android:glEsVersion="0x00020000" android:required="true" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:theme="@style/AppTheme"
        android:usesCleartextTraffic="true"
        android:networkSecurityConfig="@xml/network_security_config"
        android:hardwareAccelerated="true">

        <activity
            android:name=".MainActivity"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|smallestScreenSize|screenLayout|uiMode"
            android:exported="true"
            android:launchMode="singleTask"
            android:theme="@style/AppTheme.NoActionBarLaunch">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${{applicationId}}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>
    </application>
</manifest>'''

    try:
        with open(ANDROID_MANIFEST, 'w', encoding='utf-8') as f:
            f.write(manifest_content)
        safe_log(logbox, f"✓ AndroidManifest.xml corregido para: {nombre_paquete_limpio}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR escribiendo AndroidManifest.xml: {e}")
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

def crear_archivos_adicionales_android(logbox, backend_host=None):
    '''
    Crea archivos XML adicionales necesarios para la configuración de Android.
    '''
    xml_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "xml")
    os.makedirs(xml_dir, exist_ok=True)
    
    # 1. Crear file_paths.xml
    file_paths_content = '''<?xml version="1.0" encoding="utf-8"?>
<paths xmlns:android="http://schemas.android.com/apk/res/android">
    <external-files-path name="my_images" path="Pictures" />
    <external-files-path name="my_movies" path="Movies" />
    <cache-path name="my_cache" path="." />
    <external-path name="external_files" path="."/>
    <files-path name="files" path="."/>
</paths>'''
    
    try:
        with open(os.path.join(xml_dir, "file_paths.xml"), 'w', encoding='utf-8') as f:
            f.write(file_paths_content)
        safe_log(logbox, "✓ file_paths.xml creado")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR creando file_paths.xml: {e}")
        raise

    # 2. Crear network_security_config.xml dinámicamente
    domain_configs = '''
        <domain includeSubdomains="true">localhost</domain>
        <domain includeSubdomains="true">10.0.2.2</domain> 
        <domain includeSubdomains="true">127.0.0.1</domain>
    '''
    if backend_host:
        # Añadir el host del backend (ej. ngrok) para permitir la conexión
        domain_configs += f'\n        <domain includeSubdomains="true">{backend_host}</domain>'

    network_security_content = f'''<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">{domain_configs}
    </domain-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system"/>
            <certificates src="user"/>
        </trust-anchors>
    </base-config>
</network-security-config>'''
    
    try:
        with open(os.path.join(xml_dir, "network_security_config.xml"), 'w', encoding='utf-8') as f:
            f.write(network_security_content)
        safe_log(logbox, f"✓ network_security_config.xml creado para {backend_host or 'desarrollo local'}.")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR creando network_security_config.xml: {e}")
        raise

# --- Funciones robustas para generación de marcadores y compilación ---

def generar_network_security_config(logbox, backend_host):
    """
    Genera el archivo network_security_config.xml para permitir tráfico HTTPS al host del backend.
    """
    network_security_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "xml")
    network_security_file = os.path.join(network_security_dir, "network_security_config.xml")
    
    os.makedirs(network_security_dir, exist_ok=True)
    
    network_security_content = f"""<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config>
        <domain includeSubdomains="true">{backend_host}</domain>
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
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

def configurar_gradle_build(logbox, nombre_paquete_limpio):
    '''
    Configura el archivo build.gradle (Module: app) con las dependencias y configuraciones correctas para AR.
    '''
    gradle_file = os.path.join(ANDROID_DIR, "app", "build.gradle")
    
    # El applicationId debe coincidir con el del Manifest y capacitor.config.json
    application_id = f"com.libros3dar.{nombre_paquete_limpio}"

    gradle_content = f'''apply plugin: 'com.android.application'

android {{
    namespace "{application_id}"
    compileSdkVersion 34
    defaultConfig {{
        applicationId "{application_id}"
        minSdkVersion 24
        targetSdkVersion 34
        versionCode 1
        versionName "1.0"
        testInstrumentationRunner "androidx.test.runner.AndroidJUnitRunner"
    }}
    buildTypes {{
        release {{
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }}
    }}
    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }}
    packagingOptions {{
        exclude 'META-INF/DEPENDENCIES'
        exclude 'META-INF/LICENSE'
        exclude 'META-INF/LICENSE.txt'
        exclude 'META-INF/license.txt'
        exclude 'META-INF/NOTICE'
        exclude 'META-INF/NOTICE.txt'
        exclude 'META-INF/notice.txt'
        exclude 'META-INF/ASL2.0'
        exclude("META-INF/*.kotlin_module")
    }}
}}

repositories {{
    google()
    mavenCentral()
}}

dependencies {{
    implementation fileTree(dir: 'libs', include: ['*.jar'])
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation project(':capacitor-android')
    testImplementation 'junit:junit:4.13.2'
    androidTestImplementation 'androidx.test.ext:junit:1.1.5'
    androidTestImplementation 'androidx.test.espresso:espresso-core:3.5.1'
    implementation 'androidx.webkit:webkit:1.7.0'
}}
'''
    
    try:
        with open(gradle_file, 'w', encoding='utf-8') as f:
            f.write(gradle_content)
        safe_log(logbox, "✓ build.gradle configurado correctamente con dependencias AR.")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR configurando build.gradle: {e}")
        raise

def ensure_capacitor_js(logbox, project_dir):
    """
    Verifica si capacitor.js existe en la carpeta www y, si no, lo copia desde node_modules.
    """
    www_dir = os.path.join(project_dir, "www")
    capacitor_js_path = os.path.join(www_dir, "capacitor.js")
    
    if os.path.exists(capacitor_js_path):
        safe_log(logbox, "✓ capacitor.js ya existe en www.")
        return

    safe_log(logbox, "ADVERTENCIA: capacitor.js no encontrado en www. Intentando copia manual...")
    
    src_capacitor_js = os.path.join(project_dir, "node_modules", "@capacitor", "core", "dist", "capacitor.js")
    
    if not os.path.exists(src_capacitor_js):
        safe_log(logbox, "✗ ERROR: No se pudo encontrar el archivo fuente de capacitor.js en node_modules.")
        messagebox.showerror("Error Crítico", "No se encontró capacitor.js en node_modules. El APK no funcionará. Ejecuta 'npm install' en la carpeta del proyecto.")
        return

    try:
        shutil.copy2(src_capacitor_js, capacitor_js_path)
        safe_log(logbox, "✓ Copia manual de capacitor.js a www exitosa.")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR: Fallo al copiar manualmente capacitor.js: {e}")
        messagebox.showerror("Error de Copia", f"No se pudo copiar capacitor.js: {e}")

NFT_CREATOR_PATH = os.path.join(BASE_DIR, "tools", "NFT-Marker-Creator")

def verificar_nft_marker_creator(logbox):
    if not os.path.exists(NFT_CREATOR_PATH):
        safe_log(logbox, "ADVERTENCIA: Directorio de NFT-Marker-Creator no encontrado.")
        return False
    
    main_script_path = os.path.join(NFT_CREATOR_PATH, "MarkerCreator.js")
    alt_script_path = os.path.join(NFT_CREATOR_PATH, "src", "NFTMarkerCreator.js")
    
    if not os.path.exists(main_script_path) and not os.path.exists(alt_script_path):
        safe_log(logbox, "ADVERTENCIA: Script principal de NFT-Marker-Creator no encontrado.")
        return False

    try:
        result = subprocess.run(["node", "--version"], cwd=NFT_CREATOR_PATH, capture_output=True, text=True, shell=True, check=True)
        safe_log(logbox, f"✓ NFT-Marker-Creator verificado con Node.js {result.stdout.strip()}")
        return True
    except Exception as e:
        safe_log(logbox, f"✗ Error verificando NFT-Marker-Creator: {e}")
        return False

def generar_marcador_nft(logbox, imagen_path, nombre_marcador):
    if not verificar_nft_marker_creator(logbox):
        return False
    
    try:
        script_path = os.path.join(NFT_CREATOR_PATH, "MarkerCreator.js")
        if not os.path.exists(script_path):
            script_path = os.path.join(NFT_CREATOR_PATH, "src", "NFTMarkerCreator.js")

        imagen_absoluta = os.path.abspath(imagen_path)
        cmd = ["node", os.path.basename(script_path), "-i", imagen_absoluta]
        
        safe_log(logbox, f"Ejecutando: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=NFT_CREATOR_PATH, capture_output=True, text=True, shell=True, timeout=180)
        
        if result.returncode == 0 and "error" not in result.stderr.lower():
            output_dir = os.path.join(WWW_DIR, "assets", "markers")
            os.makedirs(output_dir, exist_ok=True)
            archivos_movidos = 0
            base_name = os.path.splitext(os.path.basename(imagen_path))[0]
            for ext in ['.fset', '.fset3', '.iset']:
                src_file = os.path.join(NFT_CREATOR_PATH, base_name + ext)
                if os.path.exists(src_file):
                    dst_file = os.path.join(output_dir, f"{nombre_marcador}{ext}")
                    shutil.move(src_file, dst_file)
                    safe_log(logbox, f"✓ Archivo NFT movido: {dst_file}")
                    archivos_movidos += 1
            return archivos_movidos > 0
        else:
            safe_log(logbox, f"✗ Error en NFT-Marker-Creator: {result.stderr or result.stdout}")
            return False
    except Exception as e:
        safe_log(logbox, f"✗ Error crítico generando marcador NFT: {e}")
        return False

def generar_patt_opencv(logbox, imagen_path, patron_path):
    try:
        img = cv2.imread(imagen_path, cv2.IMREAD_GRAYSCALE)
        if img is None: raise IOError(f"No se pudo cargar la imagen con OpenCV: {imagen_path}")
        img_resized = cv2.resize(img, (16, 16), interpolation=cv2.INTER_AREA)
        patt_content = ""
        for _ in range(3):
            for row in img_resized:
                patt_content += " ".join(f"{val:3d}" for val in row) + "\n"
            patt_content += "\n"
        with open(patron_path, 'w', encoding='utf-8') as f:
            f.write(patt_content.strip())
        safe_log(logbox, f"✓ Patrón .patt generado con OpenCV para: {os.path.basename(imagen_path)}")
        return True
    except Exception as e:
        safe_log(logbox, f"✗ Error generando .patt con OpenCV: {e}")
        return False

def diagnosticar_espacio_disco(logbox):
    '''
    Diagnostica en detalle el uso de espacio en disco
    '''
    try:
        safe_log(logbox, "=== DIAGNÓSTICO DE ESPACIO EN DISCO ===")
        
        # Verificar discos principales
        for letra in ['C:', 'D:']:
            try:
                disk = psutil.disk_usage(letra)
                total_gb = disk.total / (1024**3)
                used_gb = disk.used / (1024**3)
                free_gb = disk.free / (1024**3)
                percent_used = (used_gb / total_gb) * 100
                
                safe_log(logbox, f"Disco {letra}")
                safe_log(logbox, f"  Total: {total_gb:.1f} GB")
                safe_log(logbox, f"  Usado: {used_gb:.1f} GB ({percent_used:.1f}%)")
                safe_log(logbox, f"  Libre: {free_gb:.1f} GB")
                
                if free_gb < 4:
                    safe_log(logbox, f"  ⚠ CRÍTICO: Menos de 4GB libres")
                elif free_gb < 8:
                    safe_log(logbox, f"  ⚠ ADVERTENCIA: Menos de 8GB libres")
                else:
                    safe_log(logbox, f"  ✓ Espacio suficiente")
                    
            except Exception as e:
                safe_log(logbox, f"No se pudo verificar disco {letra}: {e}")
        
        # Verificar directorios específicos
        dirs_to_check = [
            (os.path.join(os.path.expanduser("~"), ".gradle"), "Cache Gradle Usuario"),
            (ANDROID_DIR, "Proyecto Android"),
            (os.path.join(ANDROID_DIR, "app", "build"), "Build Directory"),
        ]
        
        safe_log(logbox, "\n=== TAMAÑO DE DIRECTORIOS ===")
        for dir_path, name in dirs_to_check:
            if os.path.exists(dir_path):
                try:
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(dir_path):
                        for filename in filenames:
                            filepath = os.path.join(dirpath, filename)
                            if os.path.exists(filepath):
                                total_size += os.path.getsize(filepath)
                    
                    size_gb = total_size / (1024**3)
                    safe_log(logbox, f"{name}: {size_gb:.2f} GB")
                    
                except Exception as e:
                    safe_log(logbox, f"{name}: Error calculando tamaño - {e}")
            else:
                safe_log(logbox, f"{name}: No existe")
        
        safe_log(logbox, "=== RECOMENDACIONES ===")
        safe_log(logbox, "1. Libere espacio en disco eliminando archivos innecesarios")
        safe_log(logbox, "2. Considere mover el proyecto a un disco con más espacio")
        safe_log(logbox, "3. Limpie el cache de Gradle manualmente")
        safe_log(logbox, "4. Use 'Liberador de espacio en disco' de Windows")
        
    except ImportError:
        safe_log(logbox, "Para diagnóstico completo, instale: pip install psutil")
    except Exception as e:
        safe_log(logbox, f"Error en diagnóstico: {e}")

def verificar_espacio_disco(logbox):
    '''
    Verifica el espacio disponible en los discos críticos
    '''
    try:
        # Verificar disco C: (cache de Gradle)
        disk_c = psutil.disk_usage('C:')
        free_gb_c = disk_c.free / (1024**3)
        
        # Verificar disco D: (proyecto)
        disk_d = psutil.disk_usage('D:')
        free_gb_d = disk_d.free / (1024**3)
        
        safe_log(logbox, f"Espacio libre en C: {free_gb_c:.1f} GB")
        safe_log(logbox, f"Espacio libre en D: {free_gb_d:.1f} GB")
        
        # Se necesitan al menos 8GB libres para build de Android
        if free_gb_c < 4:
            safe_log(logbox, f"⚠ ADVERTENCIA: Poco espacio en C: ({free_gb_c:.1f} GB). Se necesitan al menos 4GB")
            return False
            
        if free_gb_d < 4:
            safe_log(logbox, f"⚠ ADVERTENCIA: Poco espacio en D: ({free_gb_d:.1f} GB). Se necesitan al menos 4GB")
            return False
            
        safe_log(logbox, "✓ Espacio en disco suficiente para build")
        return True
        
    except ImportError:
        safe_log(logbox, "⚠ No se puede verificar espacio (instale psutil): pip install psutil")
        return True
    except Exception as e:
        safe_log(logbox, f"⚠ Error verificando espacio en disco: {e}")
        return True

def configurar_gradle_en_disco_d(logbox, nombre_paquete_limpio):
    """
    Configura Gradle para usar el disco D cuando el disco C tiene poco espacio libre.
    Esta función modifica las configuraciones de Gradle para optimizar el uso de espacio en disco.
    
    Args:
        logbox: Widget de log para mostrar mensajes de estado
        nombre_paquete_limpio: El nombre del paquete para usar en el namespace.
    
    Returns:
        bool: True si la configuración fue exitosa, False en caso contrario
    """
    try:
        safe_log(logbox, "Configurando Gradle para usar disco D...")
        
        # 1. Configurar GRADLE_USER_HOME para usar disco D
        gradle_user_home = r"D:\gradle_cache"
        os.makedirs(gradle_user_home, exist_ok=True)
        
        # Establecer variable de entorno para la sesión actual
        os.environ['GRADLE_USER_HOME'] = gradle_user_home
        safe_log(logbox, f"✓ GRADLE_USER_HOME configurado en: {gradle_user_home}")
        
        # 2. Crear archivo gradle.properties en el directorio de trabajo del proyecto
        gradle_properties_path = os.path.join(PROJECT_DIR, "gradle.properties")
        gradle_properties_content = f"""# Configuración optimizada para disco D
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configureondemand=true

# Configuración de memoria optimizada
org.gradle.jvmargs=-Xmx4096m -XX:MaxPermSize=512m -XX:+HeapDumpOnOutOfMemoryError

# Directorio de cache personalizado en disco D
org.gradle.cache.dir=D:\\\\gradle_cache\\\\caches

# Configuración de Android optimizada
android.enableBuildCache=true
android.useAndroidX=true
android.enableJetifier=true

# Kotlin optimizations
kotlin.incremental=true
kotlin.incremental.usePreciseJavaTracking=true
kotlin.parallel.tasks.in.project=true
"""
        
        with open(gradle_properties_path, 'w', encoding='utf-8') as f:
            f.write(gradle_properties_content)
        safe_log(logbox, f"✓ Archivo gradle.properties creado en: {gradle_properties_path}")
        
        # 3. Configurar gradle.properties global en GRADLE_USER_HOME
        global_gradle_properties = os.path.join(gradle_user_home, "gradle.properties")
        with open(global_gradle_properties, 'w', encoding='utf-8') as f:
            f.write(gradle_properties_content)
        safe_log(logbox, f"✓ Configuración global de Gradle creada en: {global_gradle_properties}")
        
        # 4. Configurar build directory y namespace en el proyecto Android
        android_gradle_path = os.path.join(ANDROID_DIR, "app", "build.gradle")
        if os.path.exists(android_gradle_path):
            with open(android_gradle_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Comprobar si las configuraciones ya existen
            namespace_exists = any('namespace' in line for line in lines)
            builddir_exists = any('buildDir' in line for line in lines)

            if not namespace_exists or not builddir_exists:
                with open(android_gradle_path, 'w', encoding='utf-8') as f:
                    inserted = False
                    for line in lines:
                        f.write(line)
                        if 'android {' in line and not inserted:
                            if not namespace_exists:
                                f.write(f'    namespace "com.libros3dar.{nombre_paquete_limpio}"\n')
                            if not builddir_exists:
                                # Usar una ruta relativa al buildDir del proyecto para mayor portabilidad
                                f.write(f'    buildDir = file("D:/android_builds/{nombre_paquete_limpio}")\n')
                            inserted = True
                safe_log(logbox, "✓ build.gradle actualizado con namespace y buildDir.")
        
        # 5. Crear directorios necesarios en disco D
        directories_to_create = [
            r"D:\gradle_cache",
            r"D:\gradle_cache\caches", 
            r"D:\gradle_cache\wrapper",
            r"D:\android_builds",
            r"D:\android_temp"
        ]
        
        for dir_path in directories_to_create:
            os.makedirs(dir_path, exist_ok=True)
        
        safe_log(logbox, "✓ Directorios de cache creados en disco D")
        
        # 6. Configurar variables de entorno adicionales para Java/Android
        os.environ['JAVA_OPTS'] = "-Djava.io.tmpdir=D:\\android_temp"
        os.environ['GRADLE_OPTS'] = "-Djava.io.tmpdir=D:\\android_temp -Xmx4096m"
        
        safe_log(logbox, "✓ Variables de entorno configuradas para usar disco D")
        safe_log(logbox, "✓ Configuración de Gradle en disco D completada exitosamente")
        
        return True
        
    except Exception as e:
        safe_log(logbox, f"✗ ERROR configurando Gradle en disco D: {e}")
        return False

def compilar_apk_usando_disco_d(logbox, nombre_paquete_limpio):
    '''
    Versión del compilador que usa exclusivamente el disco D
    '''
    try:
        # 1. Configurar variables de entorno para usar disco D
        temp_base_dir = os.path.join(BASE_DIR, "temporal")
        os.environ['GRADLE_USER_HOME'] = os.path.join(temp_base_dir, "gradle")
        os.environ['JAVA_OPTS'] = f'-Duser.home={temp_base_dir} -Djava.io.tmpdir={os.path.join(temp_base_dir, "temp")}'
        os.environ['TEMP'] = os.path.join(temp_base_dir, "temp")
        os.environ['TMP'] = os.path.join(temp_base_dir, "temp")
        
        safe_log(logbox, f"✓ Variables de entorno configuradas para disco D")
        safe_log(logbox, f"  GRADLE_USER_HOME: {os.environ['GRADLE_USER_HOME']}")
        
        # 2. Verificar espacio una vez más
        disk_d = psutil.disk_usage('D:')
        free_gb_d = disk_d.free / (1024**3)
        safe_log(logbox, f"Espacio disponible en D: {free_gb_d:.1f} GB")
        
        if free_gb_d < 8:
            safe_log(logbox, f"⚠ ADVERTENCIA: Poco espacio en D: {free_gb_d:.1f} GB")
        
        # 3. Limpiar build anterior
        build_dir = os.path.join(ANDROID_DIR, "app", "build")
        if os.path.exists(build_dir):
            try:
                shutil.rmtree(build_dir)
                safe_log(logbox, "✓ Directorio build anterior limpiado")
            except Exception as e:
                safe_log(logbox, f"⚠ No se pudo limpiar build anterior: {e}")
        
        # 4. Configurar gradle.properties específico para disco D
        gradle_props_path = os.path.join(ANDROID_DIR, "gradle.properties")
        gradle_props_content = f'''# Configuración para usar disco D exclusivamente
org.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=256m -Dfile.encoding=UTF-8 -Djava.io.tmpdir={os.path.join(temp_base_dir, "temp").replace(os.sep, '/')}
org.gradle.daemon=false
org.gradle.parallel=false
org.gradle.caching=false
org.gradle.user.home={os.path.join(temp_base_dir, "gradle").replace(os.sep, '/')}

# Configuración Android
android.useAndroidX=true
android.enableJetifier=true
android.nonTransitiveRClass=false
android.suppressUnsupportedCompileSdk=34
'''
        
        with open(gradle_props_path, 'w', encoding='utf-8') as f:
            f.write(gradle_props_content)
        safe_log(logbox, "✓ gradle.properties actualizado para disco D")
        
        # 5. Intentar build con configuración de disco D
        max_intentos = 2
        for intento in range(1, max_intentos + 1):
            safe_log(logbox, f"=== INTENTO {intento}/{max_intentos} DE COMPILACIÓN USANDO DISCO D ===")
            
            try:
                # Preparar entorno para subprocess
                env = os.environ.copy()
                env['GRADLE_USER_HOME'] = os.path.join(temp_base_dir, "gradle")
                env['TEMP'] = os.path.join(temp_base_dir, "temp")
                env['TMP'] = os.path.join(temp_base_dir, "temp")
                env['JAVA_OPTS'] = f'-Djava.io.tmpdir={os.path.join(temp_base_dir, "temp")}'
                
                # Capacitor sync
                safe_log(logbox, "Ejecutando capacitor sync...")
                cmd_sync = ["npx", "cap", "sync", "android"]
                result = subprocess.run(
                    cmd_sync, 
                    cwd=PROJECT_DIR, 
                    capture_output=True, 
                    text=True, 
                    timeout=300,
                    env=env,
                    shell=True
                )
                
                if result.returncode != 0:
                    safe_log(logbox, f"ERROR en cap sync: {result.stderr[:500]}")
                    if intento < max_intentos:
                        safe_log(logbox, "Reintentando cap sync...")
                        time.sleep(10)
                        continue
                    return None
                
                safe_log(logbox, "✓ Capacitor sync completado")
                
                # Build de APK usando disco D
                safe_log(logbox, "Iniciando compilación de APK usando disco D...")
                
                gradle_cmd = [
                    "gradlew.bat", 
                    "assembleDebug", 
                    "--no-daemon",
                    f"--gradle-user-home={os.path.join(temp_base_dir, 'gradle')}",
                    "--stacktrace"
                ]
                
                safe_log(logbox, f"Comando: {' '.join(gradle_cmd)}")
                safe_log(logbox, f"Directorio de trabajo: {ANDROID_DIR}")
                safe_log(logbox, f"GRADLE_USER_HOME: {env['GRADLE_USER_HOME']}")
                
                result = subprocess.run(
                    gradle_cmd,
                    cwd=ANDROID_DIR,
                    capture_output=True,
                    text=True,
                    timeout=1800,  # 30 minutos
                    env=env,
                    shell=True
                )
                
                if result.returncode == 0:
                    safe_log(logbox, "✓ ¡APK COMPILADO EXITOSAMENTE USANDO DISCO D!")
                    
                    # Buscar y copiar APK desde la nueva ubicación en el disco D
                    # Esta ruta debe coincidir con la configurada en `configurar_gradle_en_disco_d`
                    new_build_dir = os.path.join("D:", os.sep, "android_builds", nombre_paquete_limpio)
                    apk_src = os.path.join(new_build_dir, "outputs", "apk", "debug", "app-debug.apk")
                    
                    if os.path.exists(apk_src):
                        apk_dst_dir = os.path.join(OUTPUT_APK_DIR, nombre_paquete_limpio)
                        os.makedirs(apk_dst_dir, exist_ok=True)
                        apk_dst_file = os.path.join(apk_dst_dir, f"{nombre_paquete_limpio}.apk")
                        
                        shutil.copy2(apk_src, apk_dst_file)
                        safe_log(logbox, f"✓ APK copiado exitosamente a: {apk_dst_file}")
                        
                        # Verificar tamaño del APK
                        apk_size_mb = os.path.getsize(apk_dst_file) / (1024 * 1024)
                        safe_log(logbox, f"✓ Tamaño del APK: {apk_size_mb:.2f} MB")
                        
                        # Limpiar archivos temporales
                        try:
                            temp_cache = os.path.join(temp_base_dir, "gradle", "caches")
                            if os.path.exists(temp_cache):
                                shutil.rmtree(temp_cache)
                                safe_log(logbox, "✓ Cache temporal limpiado")
                        except:
                            pass
                        
                        return apk_dst_file
                    else:
                        safe_log(logbox, f"✗ APK no encontrado en: {apk_src}")
                        # Listar archivos en directorio de salida para debug
                        output_dir = os.path.join(ANDROID_DIR, "app", "build", "outputs")
                        if os.path.exists(output_dir):
                            safe_log(logbox, f"Contenido de {output_dir}:")
                            for item in os.listdir(output_dir):
                                safe_log(logbox, f"  - {item}")
                else:
                    # Analizar errores
                    safe_log(logbox, f"✗ Build falló con código: {result.returncode}")
                    
                    # Buscar errores específicos
                    error_output = result.stderr + result.stdout
                    lines = error_output.split('\n')
                    
                    # Errores de espacio
                    space_errors = [line for line in lines if any(term in line.lower() for term in ['espacio', 'space', 'disk', 'no space', 'insufficient'])]
                    if space_errors:
                        safe_log(logbox, "ERRORES DE ESPACIO DETECTADOS:")
                        for error in space_errors[:3]:
                            safe_log(logbox, f"  {error.strip()}")
                    
                    # Otros errores importantes
                    important_errors = [line for line in lines if any(term in line.lower() for term in ['error:', 'exception', 'failed', 'could not'])]
                    if important_errors:
                        safe_log(logbox, "OTROS ERRORES IMPORTANTES:")
                        for error in important_errors[:5]:
                            safe_log(logbox, f"  {error.strip()}")
                    
                    # Si no se encontraron errores específicos, mostrar las últimas líneas
                    if not space_errors and not important_errors:
                        safe_log(logbox, "ÚLTIMAS LÍNEAS DE SALIDA:")
                        for line in lines[-10:]:
                            if line.strip():
                                safe_log(logbox, f"  {line.strip()}")
                
                # Pausa entre intentos
                if intento < max_intentos:
                    safe_log(logbox, f"Reintentando en 15 segundos...")
                    time.sleep(15)
                    
            except subprocess.TimeoutExpired:
                safe_log(logbox, f"✗ TIMEOUT en intento {intento} (30 minutos)")
                if intento < max_intentos:
                    safe_log(logbox, "El build tomó demasiado tiempo, reintentando...")
            except Exception as e:
                safe_log(logbox, f"✗ ERROR en intento {intento}: {str(e)}")
        
        safe_log(logbox, "======== BUILD APK FALLIDO USANDO DISCO D ========")
        return None
        
    except Exception as e:
        safe_log(logbox, f"✗ ERROR CRÍTICO en compilar_apk_usando_disco_d: {e}")
        return None

def generar_main_activity_simple(logbox, nombre_paquete_limpio, backend_url):
    """
    Genera MainActivity.java usando un template simple y confiable
    """
    try:
        # Crear estructura de directorios
        package_path = ["com", "libros3dar", nombre_paquete_limpio]
        current_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "java")
        for folder in package_path:
            current_dir = os.path.join(current_dir, folder)
            os.makedirs(current_dir, exist_ok=True)

        main_activity_path = os.path.join(current_dir, "MainActivity.java")

        # Template simple sin placeholders problemáticos
        main_activity_content = f"""package com.libros3dar.{nombre_paquete_limpio};

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{
    @Override
    public void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
    }}
}}"""

        # Escribir archivo
        with open(main_activity_path, 'w', encoding='utf-8') as f:
            f.write(main_activity_content)

        # Verificación inmediata
        if os.path.exists(main_activity_path):
            size = os.path.getsize(main_activity_path)
            safe_log(logbox, f"✓ MainActivity.java creada: {main_activity_path} ({size} bytes)")
            
            # Verificar contenido
            with open(main_activity_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if f"package com.libros3dar.{nombre_paquete_limpio};" in content:
                    safe_log(logbox, "✓ Package name verificado en MainActivity.java")
                    return True
                else:
                    safe_log(logbox, "✗ ERROR: Package name incorrecto en MainActivity.java")
                    return False
        else:
            safe_log(logbox, "✗ Error: MainActivity.java no se creó")
            return False

    except Exception as e:
        safe_log(logbox, f"✗ Error creando MainActivity: {e}")
        return False


def verificar_archivos_android_critical(logbox, nombre_paquete_limpio):
    """
    Verificación crítica antes de compilar APK
    """
    archivos_criticos = {
        "MainActivity.java": os.path.join(ANDROID_DIR, "app", "src", "main", "java", "com", "libros3dar", nombre_paquete_limpio, "MainActivity.java"),
        "AndroidManifest.xml": os.path.join(ANDROID_DIR, "app", "src", "main", "AndroidManifest.xml"),
        "build.gradle (app)": os.path.join(ANDROID_DIR, "app", "build.gradle"),
        "capacitor.config.json": os.path.join(PROJECT_DIR, "capacitor.config.json")
    }

    safe_log(logbox, "=== VERIFICACIÓN CRÍTICA DE ARCHIVOS ===")
    todos_ok = True

    for nombre, ruta in archivos_criticos.items():
        if os.path.exists(ruta):
            size = os.path.getsize(ruta)
            safe_log(logbox, f" ✓ {nombre}: {size} bytes - OK")
            
            # Verificación específica para MainActivity
            if nombre == "MainActivity.java":
                with open(ruta, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if f"package com.libros3dar.{nombre_paquete_limpio};" in content:
                        safe_log(logbox, "   ✓ Package correcto en MainActivity")
                    else:
                        safe_log(logbox, "   ✗ Package incorrecto en MainActivity")
                        todos_ok = False
        else:
            safe_log(logbox, f" ✗ {nombre}: NO EXISTE")
            todos_ok = False

    return todos_ok


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

# ---------------------- CLASE PRINCIPAL GUI ----------------------

class GeneradorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador Libros 3D AR")
        self.root.geometry("1260x900") # Tamaño de la ventana de la GUI
        self.nombre_libro = StringVar()
        # CAMBIO CLAVE AQUÍ: Asegurar que la URL del backend siempre sea HTTPS
        self.backend_url = StringVar(value="https://192.168.80.16:5000/activar") 
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
        Button(acciones_frame, text="Iniciar Servidor y Ngrok", bg="#ffc107", fg="black",
               command=self.iniciar_servidor_ngrok, width=18, height=2).pack(pady=5)

        Label(acciones_frame, text="9. Verificación:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(20, 10))
        Button(acciones_frame, text="Verificar Conexión", command=self.verify_backend_connection, width=18).pack(pady=5)
        Button(acciones_frame, text="Ver Claves en BD", command=self.view_activation_keys, width=18).pack(pady=5)

        Button(acciones_frame, text="Limpiar Formulario", fg="black",
               command=self.limpiar_todo, width=18).pack(pady=20)

        log_frame = Frame(self.root, padx=10, pady=10)
        log_frame.pack(side=RIGHT, fill=BOTH, expand=True)
        Label(log_frame, text="Log de la Aplicación:", font=("Segoe UI", 10, "bold")).pack(anchor='w')
        self.logbox = Text(log_frame, height=38, width=70, bg="#f4f4f4", state=DISABLED, font=("Consolas", 9))
        self.logbox.pack(side=LEFT, fill=BOTH, expand=True)
        Scrollbar(log_frame, command=self.logbox.yview, orient=VERTICAL).pack(side=RIGHT, fill=Y)
        self.logbox.config(yscrollcommand=lambda f, l: ()) # Deshabilita el scroll automático para evitar saltos

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
        # Asegurar que la URL se reinicie a HTTPS
        self.backend_url.set("https://www.google.com")
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

    def _generar_codigo_eco(self):
        """Genera un código de activación único con el formato ECO-XXXX-YYYY-ZZZZ."""
        parts = str(uuid.uuid4()).upper().split('-')
        return f"ECO-{parts[0][:4]}-{parts[1]}-{parts[2]}"

    def generar_paquete(self):
        """
        Genera el paquete de contenido, copia los assets, genera claves de activación
        y crea los archivos HTML para el flujo de activación y AR.
        """
        self.set_progress("Generando paquete...")
        nombre = limpiar_nombre(self.nombre_libro.get().strip())
        backend_url = self.backend_url.get().strip()

        if not backend_url.startswith("https://"):
            messagebox.showerror("Error de URL", "La URL del Backend debe comenzar con 'https://'.")
            self.set_progress("Error: URL no es HTTPS.", "red")
            return False

        try:
            cantidad = int(self.cant_claves_var.get().strip())
            if cantidad <= 0: raise ValueError("Cantidad inválida")
        except Exception:
            messagebox.showerror("Error", "Cantidad de claves inválida.")
            return False

        if not all([nombre, backend_url, self._portada_path_full]):
            messagebox.showerror("Error", "Faltan datos obligatorios (Nombre, URL Backend, Portada).")
            return False

        if not self.validar_entrada() or not any(p['imagen'] and p['modelo'] for p in self.pares):
            messagebox.showerror("Error", "Faltan archivos o no hay pares imagen-modelo completos.")
            return False

        safe_log(self.logbox, f"Iniciando creación del paquete: {nombre}")
        paquete_dir = os.path.join(PAQUETES_DIR, nombre)
        limpiar_carpetas(self.logbox, nombre)

        try:
            # 1. Copiar y procesar assets
            portada_dest_paquete = os.path.join(paquete_dir, "portada.jpg")
            with Image.open(self._portada_path_full) as img:
                img.convert("RGB").save(portada_dest_paquete, "JPEG", quality=95)
            
            # Copiar portada a www para la pantalla de activación
            shutil.copy2(portada_dest_paquete, os.path.join(WWW_DIR, "portada.jpg"))
            safe_log(self.logbox, f"✓ Portada copiada a: {portada_dest_paquete} y a www/")

            # Crear directorios para assets en www
            www_models_dir = os.path.join(WWW_DIR, "models")
            www_patterns_dir = os.path.join(WWW_DIR, "patterns")
            os.makedirs(www_models_dir, exist_ok=True)
            os.makedirs(www_patterns_dir, exist_ok=True)

            marcadores_ar_html = ""
            for par in self.pares:
                if par['imagen'] and par['modelo']:
                    # Procesar y copiar modelo 3D
                    mod_dest_paquete = os.path.join(paquete_dir, "models", f"{par['base']}.glb")
                    mod_dest_www = os.path.join(www_models_dir, f"{par['base']}.glb")
                    os.makedirs(os.path.dirname(mod_dest_paquete), exist_ok=True)
                    if os.path.splitext(par['modelo'])[1].lower() == ".glb":
                        shutil.copy2(par['modelo'], mod_dest_paquete)
                    else:
                        self.convertir_con_blender(par['modelo'], mod_dest_paquete)
                    shutil.copy2(mod_dest_paquete, mod_dest_www)
                    
                    # Copiar imagen original al paquete (para referencia)
                    img_dest_paquete = os.path.join(paquete_dir, "images", f"{par['base']}.jpg")
                    os.makedirs(os.path.dirname(img_dest_paquete), exist_ok=True)
                    shutil.copy2(par['imagen'], img_dest_paquete)

                    # --- Lógica de Generación de Marcadores Orquestada ---
                    nombre_limpio = par['base']
                    marker_type = None
                    
                    # Intento 1: Generar marcador NFT
                    if generar_marcador_nft(self.logbox, img_dest_paquete, nombre_limpio):
                        marker_type = 'nft'
                    else:
                        # Intento 2 (Fallback): Generar patrón .patt con OpenCV
                        safe_log(self.logbox, f"Fallback a OpenCV para generar patrón .patt para {nombre_limpio}")
                        patt_dest_www = os.path.join(www_patterns_dir, f"{nombre_limpio}.patt")
                        if generar_patt_opencv(self.logbox, img_dest_paquete, patt_dest_www):
                            marker_type = 'pattern'
                        else:
                            safe_log(self.logbox, f"✗ ERROR: Fallaron todos los métodos para generar un marcador para {nombre_limpio}.")

                    # Construir el HTML para este marcador según el tipo generado
                    if marker_type == 'nft':
                        descriptor_url = os.path.join("assets", "markers", nombre_limpio).replace("\\", "/")
                        model_url = os.path.join("models", f"{nombre_limpio}.glb").replace("\\", "/")
                        marcadores_ar_html += f"""
        <a-marker type='nft' descriptorurl='{descriptor_url}'>
            <a-entity gltf-model="url({model_url})" scale="0.3 0.3 0.3" animation-mixer gesture-handler></a-entity>
        </a-marker>"""
                        safe_log(self.logbox, f"✓ Marcador NFT procesado para: {nombre_limpio}")
                    elif marker_type == 'pattern':
                        pattern_url = os.path.join("patterns", f"{nombre_limpio}.patt").replace("\\", "/")
                        model_url = os.path.join("models", f"{nombre_limpio}.glb").replace("\\", "/")
                        marcadores_ar_html += f"""
        <a-marker type='pattern' url='{pattern_url}'>
            <a-entity gltf-model="url({model_url})" scale="0.3 0.3 0.3" animation-mixer gesture-handler></a-entity>
        </a-marker>"""
                        safe_log(self.logbox, f"✓ Marcador de Patrón procesado para: {nombre_limpio}")

            # 2. Generar y guardar claves
            self.claves = [self._generar_codigo_eco() for _ in range(cantidad)]
            insertar_claves_en_backend(self.logbox, self.claves)
            claves_file = os.path.join(OUTPUT_APK_DIR, f"{nombre}_claves.txt")
            with open(claves_file, "w", encoding="utf-8") as f: f.write("\n".join(self.claves))
            safe_log(self.logbox, f"✓ {cantidad} claves generadas.")

            # 3. Generar y guardar los 3 archivos HTML
            activation_html = self.generate_activation_html(nombre, backend_url)
            main_menu_html = self.generate_main_menu_html(nombre)
            ar_viewer_html = self.generate_ar_viewer_html(nombre, marcadores_ar_html)

            for filename, content in [("index.html", activation_html), ("main-menu.html", main_menu_html), ("ar-viewer.html", ar_viewer_html)]:
                with open(os.path.join(WWW_DIR, filename), "w", encoding="utf-8") as f:
                    f.write(content)
                with open(os.path.join(paquete_dir, filename), "w", encoding="utf-8") as f:
                    f.write(content)
                safe_log(self.logbox, f"✓ Archivo HTML generado y guardado: {filename}")

            # 4. Actualizar config de Capacitor
            config_path = os.path.join(PROJECT_DIR, "capacitor.config.json")
            capacitor_config = {
                "appId": f"com.libros3dar.{nombre}",
                "appName": self.nombre_libro.get().strip(),
                "webDir": "www",
                "bundledWebRuntime": False,
                "android": {
                    "allowMixedContent": True,
                    "webSecurity": False,
                    "appendUserAgent": "ARCapacitorApp/1.0"
                },
                "server": {
                    "hostname": "localhost",
                    "androidScheme": "https",
                    "cleartext": True
                },
                "plugins": {
                    "Camera": {
                        "permissions": [
                            "camera",
                            "photos"
                        ]
                    },
                    "SplashScreen": {
                        "launchShowDuration": 0
                    }
                }
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(capacitor_config, f, indent=2, ensure_ascii=False)
            safe_log(self.logbox, f"✓ capacitor.config.json actualizado con configuración AR optimizada.")

            update_strings_xml(self.logbox, self.nombre_libro.get().strip())
            self.set_progress("Paquete generado.", "green")
            return True

        except Exception as e:
            messagebox.showerror("Error al generar paquete", f"Ocurrió un error: {e}")
            self.set_progress("Error generando paquete.", "red")
            safe_log(self.logbox, f"✗ ERROR generando paquete: {e}")
            return False

    def verify_backend_connection(self):
        """Verifica la conexión con el servidor backend."""
        backend_url = self.backend_url.get().strip()
        if not backend_url:
            messagebox.showerror("Error", "La URL del Backend está vacía.")
            return

        # Use the root of the URL for the health check
        base_url = re.match(r'https?://[^/]+', backend_url).group(0)

        self.set_progress(f"Verificando conexión con {base_url}...")
        safe_log(self.logbox, f"Verificando conexión con {base_url}...")
        try:
            # We don't want to verify SSL cert for ngrok free tier, as it can be tricky.
            # For a production app, you'd want to handle this properly.
            response = requests.get(base_url, timeout=10, verify=False)
            if response.status_code == 200:
                messagebox.showinfo("Éxito", f"Conexión exitosa con el backend en {base_url}.\nRespuesta: {response.text}")
                self.set_progress("Conexión con backend exitosa.", "green")
            else:
                messagebox.showerror("Error", f"El backend respondió con un código de estado inesperado: {response.status_code}\n{response.text}")
                self.set_progress("Fallo en la conexión con backend.", "red")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error de Conexión", f"No se pudo conectar al backend en {base_url}.\nAsegúrate de que el servidor esté corriendo y la URL sea correcta.\n\nError: {e}")
            self.set_progress("Fallo en la conexión con backend.", "red")

    def view_activation_keys(self):
        """Muestra las claves de activación desde el backend con manejo robusto de errores."""
        backend_url = self.backend_url.get().strip()
        if not backend_url:
            messagebox.showerror("Error", "La URL del Backend está vacía.")
            safe_log(self.logbox, "ERROR: URL del backend no configurada")
            return
        
        try:
            # Validación y normalización de URL
            if not backend_url.startswith(('http://', 'https://')):
                backend_url = 'https://' + backend_url
                
            base_url_match = re.match(r'https?://[^/]+', backend_url)
            if not base_url_match:
                raise ValueError("Formato de URL inválido")
                
            keys_url = f"{base_url_match.group(0)}/keys"
            safe_log(self.logbox, f"Conectando a: {keys_url}")
            
            # Implementar reintentos con backoff exponencial
            for attempt in range(3):
                try:
                    timeout_duration = 10 + (attempt * 5)  # Incrementar timeout
                    response = requests.get(
                        keys_url, 
                        timeout=timeout_duration, 
                        verify=False,
                        headers={'User-Agent': 'LibrosAR-GUI/1.0'}
                    )
                    
                    safe_log(self.logbox, f"Respuesta HTTP: {response.status_code}")
                    
                    if response.status_code == 200:
                        keys = response.json()
                        # Display keys in a new window
                        top = Toplevel(self.root)
                        top.title("Claves de Activación en la Base de Datos")
                        top.geometry("600x400")
                        text = Text(top, wrap="word")
                        text.pack(expand=True, fill=BOTH)
                        text.insert(END, json.dumps(keys, indent=4))
                        self.set_progress("Claves obtenidas exitosamente.")
                        return
                    elif response.status_code == 404:
                        raise ValueError("Endpoint /keys no encontrado en el backend")
                    else:
                        safe_log(self.logbox, f"Error HTTP {response.status_code}: {response.text[:200]}")
                        
                except requests.exceptions.Timeout:
                    safe_log(self.logbox, f"Timeout en intento {attempt + 1}/3 ({timeout_duration}s)")
                    if attempt < 2:
                        time.sleep(2 ** attempt)  # Backoff exponencial
                        continue
                        
                except requests.exceptions.ConnectionError as e:
                    safe_log(self.logbox, f"Error de conexión en intento {attempt + 1}/3: {str(e)[:100]}")
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                        
            # Si llegamos aquí, todos los intentos fallaron
            raise Exception("No se pudo conectar después de 3 intentos")
            
        except Exception as e:
            error_msg = f"Error al obtener claves: {str(e)}"
            safe_log(self.logbox, error_msg)
            messagebox.showerror("Error de Conexión", error_msg)
            self.set_progress("Fallo al obtener claves.", "red")

    def generate_activation_html(self, nombre, backend_url):
        # Asegurarse de que la URL termine con /activar
        activation_url = backend_url.strip()
        if not activation_url.endswith('/activar'):
            if activation_url.endswith('/'):
                activation_url += 'activar'
            else:
                activation_url += '/activar'
        
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Activación - {nombre}</title>
    <script src="capacitor.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
        .activation-container {{ background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); text-align: center; max-width: 400px; width: 90%; }}
        .logo {{ width: 100px; height: 100px; margin: 0 auto 1rem; background: url('portada.jpg') center/cover; border-radius: 50%; }}
        input[type="text"] {{ width: 100%; padding: 1rem; border: 2px solid #ddd; border-radius: 8px; font-size: 1.1rem; margin: 1rem 0; box-sizing: border-box; }}
        .activate-btn {{ width: 100%; padding: 1rem; background: #4CAF50; color: white; border: none; border-radius: 8px; font-size: 1.1rem; cursor: pointer; transition: background 0.3s; }}
        .activate-btn:hover {{ background: #45a049; }}
        .error {{ color: #f44336; margin-top: 1rem; }} .success {{ color: #4CAF50; margin-top: 1rem; }}
    </style>
</head>
<body>
    <div class="activation-container">
        <div class="logo"></div>
        <h1>Activación Requerida</h1>
        <p>Ingresa tu código de activación para acceder al contenido AR</p>
        <input type="text" id="activationCode" placeholder="Ingresa código de activación" maxlength="19">
        <button class="activate-btn" onclick="validateCode()">Activar</button>
        <div id="message"></div>
    </div>
    <script>
        async function getOrCreateDeviceId() {{
            let deviceId = localStorage.getItem('device_id');
            if (deviceId) return deviceId;

            if (window.Capacitor && Capacitor.Plugins && Capacitor.Plugins.Device) {{
                try {{
                    const info = await Capacitor.Plugins.Device.getId();
                    deviceId = info.uuid;
                }} catch (e) {{
                    console.warn('Capacitor Device plugin failed. Using browser-based fingerprint.', e);
                }}
            }}
            
            if (!deviceId) {{
                const deviceInfo = navigator.userAgent + navigator.language + (screen.width || 0) + (screen.height || 0);
                let hash = 0;
                for (let i = 0; i < deviceInfo.length; i++) {{
                    const char = deviceInfo.charCodeAt(i);
                    hash = ((hash << 5) - hash) + char;
                    hash |= 0;
                }}
                deviceId = 'dev-' + Math.abs(hash).toString(16);
            }}

            localStorage.setItem('device_id', deviceId);
            return deviceId;
        }}
        
        document.addEventListener('deviceready', () => {{
            if (localStorage.getItem('app_activated') === 'true') {{
                window.location.href = 'main-menu.html';
            }}
        }});
        
        async function validateCode() {{
            const code = document.getElementById('activationCode').value.trim().toUpperCase();
            const messageDiv = document.getElementById('message');
            messageDiv.innerHTML = 'Validando...';

            if (!code) {{
                messageDiv.innerHTML = '<p class="error">Por favor ingresa un código</p>';
                return;
            }}

            try {{
                const deviceId = await getOrCreateDeviceId();
                const payload = {{ token: code, device_id: deviceId }};
                let result;

                if (window.Capacitor && Capacitor.isNativePlatform() && Capacitor.Plugins.CapacitorHttp) {{
                    const {{ CapacitorHttp }} = Capacitor.Plugins;
                    const response = await CapacitorHttp.request({{
                        url: '{activation_url}',
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'Accept': 'application/json' }},
                        data: payload
                    }});
                    result = response.data;
                }} else {{
                    const response = await fetch('{activation_url}', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(payload)
                    }});
                    if (!response.ok) throw new Error(`HTTP error! status: ${{response.status}}`);
                    result = await response.json();
                }}

                if (result.valid) {{
                    messageDiv.innerHTML = '<p class="success">¡Código válido! Redirigiendo...</p>';
                    localStorage.setItem('app_activated', 'true');
                    localStorage.setItem('activation_code', code);
                    setTimeout(() => {{ window.location.href = 'main-menu.html'; }}, 1500);
                }} else {{
                    messageDiv.innerHTML = `<p class="error">${{result.error || 'Código inválido o ya utilizado.'}}</p>`;
                }}
            }} catch (error) {{
                messageDiv.innerHTML = '<p class="error">Error de conexión. Verifica tu internet y la URL del servidor.</p>';
                console.error('Error de activación:', error);
            }}
        }}
    </script>
</body>
</html>"""

    def generate_main_menu_html(self, nombre):
        explicacion_btn_html = f'<button class="menu-btn explanation-btn" onclick="openExplanation()">💡 Explicación</button>' if self.explicacion_var.get().strip() else ''
        open_explanation_js = f"function openExplanation() {{ window.open('{self.explicacion_var.get().strip()}', '_blank'); }}" if self.explicacion_var.get().strip() else 'function openExplanation() {}'
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{nombre} - Menú Principal</title>
    <script src="capacitor.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 2rem; }}
        .menu-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; padding: 2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
        .menu-btn {{ width: 100%; padding: 1.5rem; margin: 1rem 0; border: none; border-radius: 10px; font-size: 1.2rem; cursor: pointer; transition: transform 0.3s, box-shadow 0.3s; }}
        .menu-btn:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }}
        .video-btn {{ background: #2196F3; color: white; }} .explanation-btn {{ background: #FF9800; color: white; }}
        .ar-btn {{ background: linear-gradient(45deg, #4CAF50, #45a049); color: white; font-weight: bold; font-size: 1.4rem; }}
    </style>
</head>
<body>
    <div class="menu-container">
        <h1 style="text-align: center; color: #333;">Bienvenido a {nombre}</h1>
        <button class="menu-btn video-btn" onclick="openVideo()">📢 Ver Video Promocional</button>
        {explicacion_btn_html}
        <button class="menu-btn ar-btn" onclick="startAR()">📱 Iniciar Realidad Aumentada</button>
    </div>
    <script>
        function openVideo() {{ window.open('{self.propaganda_var.get().strip()}', '_blank'); }}
        {open_explanation_js}
        
        async function startAR() {{
            if (localStorage.getItem('app_activated') !== 'true') {{
                alert('Sesión expirada. Redirigiendo a activación...');
                window.location.href = 'index.html';
                return;
            }}

            if (typeof Capacitor !== 'undefined' && Capacitor.isNativePlatform() && Capacitor.Plugins && Capacitor.Plugins.Camera) {{
                try {{
                    const status = await Capacitor.Plugins.Camera.requestPermissions();
                    if (status.camera === 'granted') {{
                        console.log("Permiso de cámara concedido. Iniciando AR...");
                        window.location.href = 'ar-viewer.html';
                    }} else {{
                        alert('El permiso para usar la cámara es necesario para la Realidad Aumentada.');
                    }}
                }} catch (e) {{
                    console.error("Error pidiendo permisos de cámara con Capacitor, intentando de todas formas.", e);
                    window.location.href = 'ar-viewer.html';
                }}
            }} else {{
                // Fallback para web o si el plugin no está disponible
                console.log("Usando WebRTC para navegador, o Capacitor no está listo.");
                window.location.href = 'ar-viewer.html';
            }}
        }}
    </script>
</body>
</html>"""

    def generate_ar_viewer_html(self, nombre, marcadores_ar_html):
        # El HTML proporcionado en el análisis es el más completo y robusto.
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>AR Experience - {nombre}</title>
    <script src="https://aframe.io/releases/1.3.0/aframe.min.js"></script>
    <script src="https://raw.githack.com/AR-js-org/AR.js/master/aframe/build/aframe-ar.js"></script>
    <style>
        body {{ margin: 0; font-family: Arial, sans-serif; overflow: hidden; }}
        .arjs-loader {{
            height: 100%; width: 100%; position: absolute; top: 0; left: 0;
            background-color: rgba(0, 0, 0, 0.8); z-index: 9999;
            display: flex; justify-content: center; align-items: center;
        }}
        .arjs-loader div {{
            text-align: center; font-size: 1.25em; color: white;
        }}
    </style>
</head>
<body>
    <div class="arjs-loader">
        <div>Cargando AR, por favor espere...</div>
    </div>
    
    <a-scene
        embedded
        arjs="sourceType: webcam; debugUIEnabled: false; trackingMethod: best;"
        vr-mode-ui="enabled: false;"
        renderer="logarithmicDepthBuffer: true; colorManagement: true; sortObjects: true;"
        gesture-detector
        id="scene">
        
        {marcadores_ar_html}
        
        <a-entity camera></a-entity>
    </a-scene>

    <script>
        AFRAME.registerComponent('gesture-handler', {{
            schema: {{
                enabled: {{ default: true }},
                rotationFactor: {{ default: 5 }},
                minScale: {{ default: 0.3 }},
                maxScale: {{ default: 8 }},
            }},
            init: function () {{
                this.handleScale = this.handleScale.bind(this);
                this.handleRotation = this.handleRotation.bind(this);
                this.isVisible = false;
                this.initialScale = this.el.object3D.scale.clone();
                this.scaleFactor = 1;
                this.el.sceneEl.addEventListener('markerFound', () => (this.isVisible = true));
                this.el.sceneEl.addEventListener('markerLost', () => (this.isVisible = false));
            }},
            play: function () {{
                if (this.data.enabled) {{
                    this.el.sceneEl.addEventListener('onefingermove', this.handleRotation);
                    this.el.sceneEl.addEventListener('twofingermove', this.handleScale);
                }}
            }},
            pause: function () {{
                this.el.sceneEl.removeEventListener('onefingermove', this.handleRotation);
                this.el.sceneEl.removeEventListener('twofingermove', this.handleScale);
            }},
            handleRotation: function (event) {{
                if (this.isVisible) {{
                    this.el.object3D.rotation.y += event.detail.positionChange.x * this.data.rotationFactor;
                    this.el.object3D.rotation.x += event.detail.positionChange.y * this.data.rotationFactor;
                }}
            }},
            handleScale: function (event) {{
                if (this.isVisible) {{
                    this.scaleFactor *= 1 + event.detail.spreadChange / event.detail.startSpread;
                    this.scaleFactor = Math.min(Math.max(this.scaleFactor, this.data.minScale), this.data.maxScale);
                    this.el.object3D.scale.x = this.scaleFactor * this.initialScale.x;
                    this.el.object3D.scale.y = this.scaleFactor * this.initialScale.y;
                    this.el.object3D.scale.z = this.scaleFactor * this.initialScale.z;
                }}
            }}
        }});

        AFRAME.registerComponent('gesture-detector', {{
            init: function () {{
                this.internalState = {{ previousState: null }};
                this.emitGestureEvent = this.emitGestureEvent.bind(this);
                this.el.sceneEl.addEventListener('touchstart', this.updateState.bind(this));
                this.el.sceneEl.addEventListener('touchmove', this.updateState.bind(this));
                this.el.sceneEl.addEventListener('touchend', (evt) => {{
                    this.internalState.previousState = null;
                }});
            }},
            updateState: function(event) {{
                const currentState = this.getTouchState(event);
                const previousState = this.internalState.previousState;
                const gestureContinues = previousState && currentState && currentState.touchCount === previousState.touchCount;
                if (!gestureContinues) {{
                    this.internalState.previousState = currentState;
                    return;
                }}
                const eventName = ({{1: 'one', 2: 'two'}})[currentState.touchCount] + 'fingermove';
                this.emitGestureEvent(eventName, currentState);
                this.internalState.previousState = currentState;
            }},
            getTouchState: function(event) {{
                if (event.touches.length === 0) return null;
                const touch1 = event.touches[0];
                const touch2 = event.touches.length > 1 ? event.touches[1] : null;
                const spread = touch2 ? Math.hypot(touch1.pageX - touch2.pageX, touch1.pageY - touch2.pageY) : 0;
                return {{
                    touchCount: event.touches.length,
                    position: {{ x: touch1.pageX, y: touch1.pageY }},
                    spread: spread,
                    positionChange: this.internalState.previousState ? {{
                        x: touch1.pageX - this.internalState.previousState.position.x,
                        y: touch1.pageY - this.internalState.previousState.position.y,
                    }} : {{x: 0, y: 0}},
                    startSpread: this.internalState.previousState ? this.internalState.previousState.spread : 0,
                    spreadChange: spread - (this.internalState.previousState ? this.internalState.previousState.spread : 0),
                }};
            }},
            emitGestureEvent: function(eventName, state) {{
                this.el.sceneEl.emit(eventName, state);
            }}
        }});

        window.addEventListener('arjs-video-loaded', () => {{
            document.querySelector('.arjs-loader').style.display = 'none';
        }});
    </script>
</body>
</html>"""

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
        nombre = limpiar_nombre(self.nombre_libro.get().strip())
        if not nombre:
            messagebox.showerror("Error", "El nombre del paquete está vacío.")
            return

        # 1. Preparar el proyecto limpio desde la plantilla ANTES de cualquier otra cosa.
        preparar_proyecto_capacitor(self.logbox)

        # 2. Ahora que el proyecto existe, verificar el espacio y configurar si es necesario.
        if not verificar_espacio_disco(self.logbox):
            safe_log(self.logbox, "⚠ Configurando automáticamente Gradle para usar disco D...")
            if not configurar_gradle_en_disco_d(self.logbox, nombre):
                messagebox.showerror("Error", "No se pudo configurar Gradle para usar disco D")
                return
            else:
                safe_log(self.logbox, "✓ La configuración de Gradle para usar el disco D parece haber funcionado.")

        # 3. Realizar el resto de las operaciones sobre el proyecto ya copiado y configurado.
        diagnosticar_espacio_disco(self.logbox)

        libro_dir = os.path.join(PAQUETES_DIR, nombre)
        if not os.path.exists(libro_dir):
             messagebox.showerror("Error", f"No se encontró el paquete de contenido para '{nombre}'. Por favor, 'Generar Paquete' primero.")
             return

        paquete_www_dir = os.path.join(libro_dir)
        capacitor_www_dir = WWW_DIR
        if os.path.exists(capacitor_www_dir): shutil.rmtree(capacitor_www_dir)
        shutil.copytree(paquete_www_dir, capacitor_www_dir, dirs_exist_ok=True)
        safe_log(self.logbox, f"✓ Contenido web copiado a '{capacitor_www_dir}'.")
        
        try:
            backend_url_gui = self.backend_url.get().strip()
            backend_host = re.search(r'https?://([^:/]+)', backend_url_gui).group(1) if re.search(r'https?://([^:/]+)', backend_url_gui) else None
            
            crear_archivos_adicionales_android(self.logbox, backend_host)
            
            # USAR LA FUNCIÓN SIMPLE Y VERIFICAR
            if not generar_main_activity_simple(self.logbox, nombre, backend_url_gui):
                raise Exception("No se pudo crear MainActivity.java")
        
            # VERIFICACIÓN CRÍTICA ANTES DE COMPILAR
            if not verificar_archivos_android_critical(self.logbox, nombre):
                raise Exception("Verificación de archivos críticos falló. Abortando.")

            self.generar_iconos()
            
        except Exception as e:
            self.set_progress("Error durante la configuración de Android.", "red")
            messagebox.showerror("Error de Configuración", f"Falló la configuración: {e}")
            return
        
        self.set_progress(f"Iniciando compilación del APK para '{nombre}'...")
        
        try:
            threading.Thread(target=self.build_flow_thread, args=(nombre,), daemon=True).start()
        except Exception as e:
            safe_log(self.logbox, f"✗ ERROR CRÍTICO al iniciar el hilo de compilación: {e}")
            messagebox.showerror("Error Crítico", f"No se pudo iniciar el proceso: {e}")

    def build_flow_thread(self, nombre_paquete_limpio):
        """
        Hilo principal que coordina la instalación de plugins y la compilación unificada del APK.
        """
        self.set_progress(f"Compilando APK para '{nombre_paquete_limpio}'...")
        safe_log(self.logbox, "======== INICIANDO FLUJO DE BUILD DE APK ========")

        try:
            safe_log(self.logbox, "Ejecutando 'npm install'...")
            subprocess.run("npm install", cwd=PROJECT_DIR, check=True, shell=True, capture_output=True, text=True)
            safe_log(self.logbox, "✓ Dependencias de npm instaladas.")
            
            # Usar la nueva función para compilar usando el disco D
            apk_path = compilar_apk_usando_disco_d(self.logbox, nombre_paquete_limpio)

            if apk_path:
                final_apk_dest_dir = os.path.join(OUTPUT_APK_DIR, nombre_paquete_limpio)
                claves_str = "\n".join(self.claves) if self.claves else ""
                if claves_str:
                    clave_file = os.path.join(final_apk_dest_dir, "claves-activacion.txt")
                    with open(clave_file, "w", encoding="utf-8") as f:
                        f.write(claves_str)
                    safe_log(self.logbox, f"✓ Archivo de claves creado en: {clave_file}")
                
                self.set_progress("✅ ¡APK generado y build terminado!", "green")
                safe_log(self.logbox, "======== BUILD APK COMPLETADO ========")
                messagebox.showinfo("Éxito", f"APK generado y copiado a: {apk_path}")
            else:
                self.set_progress("✗ Build de APK fallido.", "red")
                safe_log(self.logbox, "======== BUILD APK FALLIDO ========")
                messagebox.showerror("Error de compilación", "La compilación del APK falló. Revisa el log.")

        except Exception as e:
            safe_log(self.logbox, f"✗ Error crítico en build_flow_thread: {e}")
            messagebox.showerror("Error Crítico", f"Error inesperado durante la compilación: {e}")

    def iniciar_servidor_ngrok(self):
        """Inicia el servidor Flask y el túnel de ngrok en un hilo separado."""
        safe_log(self.logbox, "Iniciando servidor local y túnel de ngrok...")
        self.set_progress("Iniciando servidor y ngrok...")
        # Run in a separate thread to not block the GUI
        threading.Thread(target=self._run_server_and_ngrok_thread, daemon=True).start()

    def _run_server_and_ngrok_thread(self):
        """
        El hilo que realmente corre el servidor y ngrok.
        """
        if not os.path.exists(WWW_DIR) or not os.listdir(WWW_DIR):
            safe_log(self.logbox, "✗ ERROR: El directorio 'www' está vacío. Genere un paquete primero.")
            self.set_progress("Error: Directorio 'www' vacío.", "red")
            messagebox.showerror("Error", "El directorio 'www' está vacío. Por favor, genere un paquete antes de iniciar el servidor.")
            return

        # Define a simple Flask app to serve the 'www' directory
        app = Flask(__name__)

        @app.route('/<path:path>')
        def serve_static(path):
            return send_from_directory(WWW_DIR, path)

        @app.route('/')
        def serve_index():
            return send_from_directory(WWW_DIR, 'index.html')
        
        @app.route('/activar', methods=['POST'])
        def activar_ruta():
            # Simulación de la respuesta del backend para pruebas locales
            return jsonify({"valid": True, "message": "Activado exitosamente (simulado)"})

        # Start Flask in a separate thread, ensuring debug/reloader are off to prevent threading issues.
        flask_thread = threading.Thread(target=lambda: app.run(port=5001, host='0.0.0.0', debug=False, use_reloader=False), daemon=True)
        flask_thread.start()
        safe_log(self.logbox, "✓ Servidor Flask de prueba iniciado en http://localhost:5001")
        
        # Start ngrok tunnel
        try:
            # You might need to add your ngrok authtoken via the command line first:
            # ngrok config add-authtoken <YOUR_TOKEN>
            public_url = ngrok.connect(5001, "http")
            ngrok_url = public_url.public_url
            safe_log(self.logbox, f"✓ Túnel de ngrok creado. URL pública: {ngrok_url}")
            safe_log(self.logbox, "-> Usa esta URL en el campo 'URL Backend' para pruebas en dispositivos.")
            self.set_progress("Servidor y ngrok iniciados.", "green")
            
            # Update the backend_url entry with the new ngrok url for the activation endpoint
            self.backend_url.set(f"{ngrok_url}/activar")

        except Exception as e:
            safe_log(self.logbox, f"✗ ERROR al iniciar ngrok: {e}")
            safe_log(self.logbox, "  Asegúrate de que ngrok esté instalado y que tu authtoken esté configurado globalmente.")
            self.set_progress("Error al iniciar ngrok.", "red")
            messagebox.showerror("Error de Ngrok", f"No se pudo iniciar ngrok. Asegúrate de que esté configurado correctamente.\nError: {e}")

if __name__ == "__main__":
    root = Tk()
    app = GeneradorGUI(root)
    root.mainloop()
