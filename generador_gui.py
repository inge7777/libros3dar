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
    from flask_cors import CORS
    from pyngrok import ngrok
    import cv2
    import numpy as np
    import psutil # Para verificar el espacio en disco
except ImportError:
    print("Dependencias críticas no encontradas. Intentando instalar...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Flask", "pyngrok", "opencv-python", "numpy", "Pillow", "psutil", "flask-cors"])
    from flask import Flask, send_from_directory, jsonify
    from flask_cors import CORS
    from pyngrok import ngrok
    import cv2
    import numpy as np
    import psutil

# ---------------- RUTAS BASE ----------------
# Directorio base donde se encuentran todos los proyectos y salidas
BASE_DIR = r"F:\linux\3d-AR"
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
BLENDER_PATH = r"F:\linux\blender\blender-4.5.1-windows-x64\blender.exe"
NFT_CREATOR_PATH = os.path.join(BASE_DIR, "nft-creator")

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
    y paquetes Java/Android, eliminando caracteres problemáticos y convirtiendo a minúsculas.
    """
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode()
    # Elimina cualquier carácter que no sea alfanumérico o guion bajo
    s = re.sub(r'[^a-zA-Z0-9_]', '', s)
    # Retorna en minúsculas y limitado en longitud
    return s.lower()[:50]

def get_package_name(nombre_limpio: str) -> str:
    """Genera el nombre del paquete de Android."""
    return f"com.librosdar.{nombre_limpio}"

def actualizar_buildgradle_con_rutadinamica(nombre_paquete_limpio, logbox):
    build_gradle_path = os.path.join(ANDROID_DIR, "app", "build.gradle")
    if not os.path.exists(build_gradle_path):
        safe_log(logbox, f"✗ ERROR: No se encuentra {build_gradle_path}")
        return False

    try:
        with open(build_gradle_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        # Construimos la nueva línea con la ruta dinámica
        nueva_linea_builddir = f'    buildDir = file("F:/linux/3d-AR/android_builds/{nombre_paquete_limpio}")'

        # Reemplazamos la línea buildDir si existe, si no, la insertamos justo después de la línea "android {"
        if re.search(r'^\s*buildDir\s*=.*$', contenido, flags=re.MULTILINE):
            contenido_modificado = re.sub(r'^\s*buildDir\s*=.*$', nueva_linea_builddir, contenido, flags=re.MULTILINE)
        else:
            contenido_modificado = re.sub(r'^android\s*\{', f'android {{\n{nueva_linea_builddir}', contenido, flags=re.MULTILINE)

        with open(build_gradle_path, "w", encoding="utf-8") as f:
            f.write(contenido_modificado)

        safe_log(logbox, f"✓ build.gradle actualizado con buildDir dinámico para: {nombre_paquete_limpio}")
        return True

    except Exception as e:
        safe_log(logbox, f"✗ ERROR modificando build.gradle: {e}")
        return False

def preparar_rutas_java(package_name):
    java_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "java", *package_name.split('.'))
    os.makedirs(java_dir, exist_ok=True)
    return os.path.join(java_dir, "MainActivity.java")

def crear_main_activity(logbox, package_name):
    ruta_main_activity = preparar_rutas_java(package_name)
    codigo_java_template = """package {package_name};

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{ }}
"""
    codigo_java = codigo_java_template.format(package_name=package_name)
    try:
        with open(ruta_main_activity, "w", encoding="utf-8") as f:
            f.write(codigo_java)
        safe_log(logbox, f"✓ MainActivity.java (versión mínima) generado en: {ruta_main_activity}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR CRÍTICO generando MainActivity.java: {e}")
        raise

def actualizar_capacitor_config(logbox, package_name, app_name):
    config_path = os.path.join(PROJECT_DIR, "capacitor.config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {{}}
        
        config["appId"] = package_name
        config["appName"] = app_name
        if "webDir" not in config:
             config["webDir"] = "www"

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        safe_log(logbox, f"✓ capacitor.config.json actualizado con appId: {package_name}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR actualizando capacitor.config.json: {e}")

def set_gradle_namespace(logbox, package_name):
    build_gradle_path = os.path.join(ANDROID_DIR, "app", "build.gradle")
    if not os.path.exists(build_gradle_path):
        safe_log(logbox, f"✗ ERROR: No se encuentra {build_gradle_path}")
        return False
    with open(build_gradle_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    new_lines = []
    namespace_found = False
    # Check if namespace is already present and replace it
    if any("namespace" in line for line in lines):
        for line in lines:
            if line.strip().startswith("namespace"):
                new_lines.append(f'    namespace "{package_name}"\n')
                namespace_found = True
            else:
                new_lines.append(line)
    
    # If not present, add it
    if not namespace_found:
        final_lines = []
        for line in lines:
            final_lines.append(line)
            if "android {" in line.strip():
                final_lines.append(f'    namespace "{package_name}"\n')
        new_lines = final_lines

    with open(build_gradle_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    safe_log(logbox, f"✓ build.gradle actualizado con namespace: {package_name}")
    return True

def ensure_camera_para_dat(logbox, www_data_dir):
    """
    Asegura que el archivo camera_para.dat exista en el directorio www/data.
    Implementa una estrategia de tres niveles:
    1. Copia desde una carpeta local.
    2. Descarga desde una URL primaria.
    3. Descarga desde una URL de respaldo.
    """
    camera_para_dest_path = os.path.join(www_data_dir, "camera_para.dat")
    if os.path.exists(camera_para_dest_path):
        safe_log(logbox, "✓ `camera_para.dat` ya existe en el directorio de destino.")
        return True

    # --- Estrategia 1: Copiar desde la carpeta local ---
    local_source_path = r"F:\linux\3d-AR\camara\camera_para.dat"
    if os.path.exists(local_source_path):
        try:
            shutil.copy2(local_source_path, camera_para_dest_path)
            safe_log(logbox, f"✓ `camera_para.dat` copiado exitosamente desde la fuente local: {local_source_path}")
            return True
        except Exception as e:
            safe_log(logbox, f"ADVERTENCIA: Falló la copia local de `camera_para.dat`, aunque el archivo existe. Error: {e}")
    else:
        safe_log(logbox, "INFO: No se encontró `camera_para.dat` en la ruta local. Procediendo a descargar.")

    # --- Estrategia 2 & 3: Descargar desde URLs ---
    urls = [
        "https://jeromeetienne.github.io/AR.js/data/data/camera_para.dat",  # URL Primaria (correcta)
        "https://raw.githubusercontent.com/AR-js-org/AR.js/master/data/camera_para.dat" # URL de Respaldo
    ]

    for i, url in enumerate(urls):
        safe_log(logbox, f"Intentando descargar `camera_para.dat` desde: {url} (Intento {i+1}/{len(urls)})...")
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            with open(camera_para_dest_path, "wb") as f:
                f.write(response.content)
            safe_log(logbox, f"✓ `camera_para.dat` descargado y guardado exitosamente desde la URL {i+1}.")
            return True
        except requests.exceptions.RequestException as e:
            safe_log(logbox, f"✗ Falló la descarga desde la URL {i+1}: {e}")
            if i < len(urls) - 1:
                safe_log(logbox, "Probando con la siguiente URL de respaldo...")

    # --- Si todo falla ---
    safe_log(logbox, "✗ ERROR CRÍTICO: Fallaron todos los métodos para obtener `camera_para.dat` (copia local y descarga).")
    messagebox.showerror("Error Crítico", "No se pudo obtener `camera_para.dat` desde la fuente local ni desde internet. La funcionalidad AR no funcionará. Verifica tu conexión y la disponibilidad del archivo.")
    return False

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

def corregir_android_manifest(logbox, package_name):
    '''
    Reconstruye AndroidManifest.xml con el package name correcto y todos los permisos
    y features necesarios para AR.
    '''
    if not os.path.exists(os.path.dirname(ANDROID_MANIFEST)):
        safe_log(logbox, f"Error: El directorio para AndroidManifest.xml no existe. Abortando.")
        return

    # El namespace ahora se define exclusivamente en build.gradle.
    # Se elimina el atributo 'package' del manifest para cumplir con las nuevas
    # directivas del Android Gradle Plugin.
    manifest_content = f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Permisos completos para AR, Cámara, Audio y Bluetooth (Android 12+) -->
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.BLUETOOTH" android:maxSdkVersion="30" />
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />

    <!-- Features de hardware requeridos y opcionales -->
    <uses-feature android:name="android.hardware.camera" android:required="true" />
    <uses-feature android:name="android.hardware.camera.autofocus" android:required="false"/>
    <uses-feature android:name="android.hardware.camera.ar" android:required="true" />
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

        <meta-data android:name="com.google.ar.core" android:value="required" />

        <activity
            android:name=".MainActivity"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|smallestScreenSize|screenLayout|uiMode"
            android:exported="true"
            android:launchMode="singleTask"
            android:theme="@style/Theme.SplashScreen">
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
        safe_log(logbox, f"✓ AndroidManifest.xml corregido para: {package_name}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR escribiendo AndroidManifest.xml: {e}")
        raise


def generar_root_build_gradle(logbox):
    """
    Genera un archivo build.gradle de raíz para el proyecto Android,
    estableciendo versiones consistentes y modernas para el Android Gradle Plugin y otras dependencias.
    """
    root_gradle_path = os.path.join(ANDROID_DIR, "build.gradle")
    
    # Plantilla para el build.gradle raíz.
    # Especifica versiones modernas y compatibles de AGP y Kotlin.
    root_gradle_template = """
// Top-level build file where you can add configuration options common to all sub-projects/modules.
buildscript {
    ext {
        androidxAppCompatVersion = '1.6.1'
        androidxCoreVersion = '1.12.0'
        androidxJunitVersion = '1.1.5'
        androidxEspressoCoreVersion = '3.5.1'
        androidxWebkitVersion = '1.10.0'
        junitVersion = '4.13.2'
        // Versión del Android Gradle Plugin
        agpVersion = '8.2.1' 
    }
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath "com.android.tools.build:gradle:$agpVersion"
    }
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

task clean(type: Delete) {
    delete rootProject.buildDir
}
"""
    
    try:
        with open(root_gradle_path, 'w', encoding='utf-8') as f:
            f.write(root_gradle_template)
        safe_log(logbox, f"✓ build.gradle raíz generado exitosamente en: {root_gradle_path}")
        return True
    except Exception as e:
        safe_log(logbox, f"✗ ERROR CRÍTICO al generar el build.gradle raíz: {e}")
        return False

def generar_build_gradle_completo(logbox, package_name):
    """
    Genera un archivo build.gradle completo y robusto para el módulo :app,
    asegurando que todas las dependencias, incluido el plugin de cámara, estén presentes.
    """
    gradle_file_path = os.path.join(ANDROID_DIR, "app", "build.gradle")
    
    # Plantilla para el build.gradle. Se usa .format() para insertar el package_name.
    gradle_template = """
apply plugin: 'com.android.application'

android {{
    namespace "{package_name}"
    compileSdkVersion 34
    defaultConfig {{
        applicationId "{package_name}"
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
    implementation 'androidx.core:core-ktx:1.12.0'
    implementation project(':capacitor-android')
    testImplementation 'junit:junit:4.13.2'
    androidTestImplementation 'androidx.test.ext:junit:1.1.5'
    androidTestImplementation 'androidx.test.espresso:espresso-core:3.5.1'
    implementation 'androidx.webkit:webkit:1.10.0'
    
    // Dependencia explícita para el plugin de cámara de Capacitor
    implementation project(':capacitor-camera')
}}
"""
    
    try:
        # Formatear la plantilla con el nombre del paquete
        gradle_content = gradle_template.format(package_name=package_name)
        
        # Escribir el contenido al archivo, sobrescribiendo cualquier versión anterior
        with open(gradle_file_path, 'w', encoding='utf-8') as f:
            f.write(gradle_content)
            
        safe_log(logbox, f"✓ build.gradle completo generado exitosamente en: {gradle_file_path}")
        return True
    except Exception as e:
        safe_log(logbox, f"✗ ERROR CRÍTICO al generar build.gradle: {e}")
        return False


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

def configurar_gradle_build(logbox, package_name):
    '''
    Configura el archivo build.gradle (Module: app) con las dependencias y configuraciones correctas para AR.
    '''
    gradle_file = os.path.join(ANDROID_DIR, "app", "build.gradle")
    
    # El applicationId y el namespace deben ser consistentes en todo el proyecto.
    application_id = package_name

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
        safe_log(logbox, f"✗ ERROR: Fallo al copiar manually capacitor.js: {e}")
        messagebox.showerror("Error de Copia", f"No se pudo copiar capacitor.js: {e}")

def verificar_nft_marker_creator(logbox):
    if not os.path.exists(NFT_CREATOR_PATH):
        safe_log(logbox, "ADVERTENCIA: Directorio de NFT-Marker-Creator no encontrado.")
        return False
    
    # El script principal correcto, según la investigación, es app.js
    main_script_path = os.path.join(NFT_CREATOR_PATH, "app.js")
    
    if not os.path.exists(main_script_path):
        safe_log(logbox, f"ADVERTENCIA: No se encontró el script principal 'app.js' en {NFT_CREATOR_PATH}.")
        return False

    try:
        result = subprocess.run(["node", "--version"], cwd=NFT_CREATOR_PATH, capture_output=True, text=True, shell=True, check=True)
        safe_log(logbox, f"✓ NFT-Marker-Creator verificado con Node.js {result.stdout.strip()}")
        return True
    except Exception as e:
        safe_log(logbox, f"✗ Error verificando NFT-Marker-Creator: {e}")
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
        for letra in ['C:', 'F:']:
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
        
        # Verificar disco F: (proyecto)
        disk_f = psutil.disk_usage('F:')
        free_gb_f = disk_f.free / (1024**3)
        
        safe_log(logbox, f"Espacio libre en C: {free_gb_c:.1f} GB")
        safe_log(logbox, f"Espacio libre en F: {free_gb_f:.1f} GB")
        
        # Se necesitan al menos 8GB libres para build de Android
        if free_gb_c < 4:
            safe_log(logbox, f"⚠ ADVERTENCIA: Poco espacio en C: ({free_gb_c:.1f} GB). Se necesitan al menos 4GB")
            return False
            
        if free_gb_f < 4:
            safe_log(logbox, f"⚠ ADVERTENCIA: Poco espacio en F: ({free_gb_f:.1f} GB). Se necesitan al menos 4GB")
            return False
            
        safe_log(logbox, "✓ Espacio en disco suficiente para build")
        return True
        
    except ImportError:
        safe_log(logbox, "⚠ No se puede verificar espacio (instale psutil): pip install psutil")
        return True
    except Exception as e:
        safe_log(logbox, f"⚠ Error verificando espacio en disco: {e}")
        return True

def configurar_gradle_en_disco_f(logbox, nombre_paquete_limpio):
    """
    Configura Gradle para usar el disco F de forma robusta, asegurando que el
    buildDir se establezca dinámicamente en el archivo build.gradle.
    """
    try:
        safe_log(logbox, "Iniciando configuración de Gradle para usar disco F...")

        # --- 1. Crear directorios necesarios en disco F ---
        gradle_user_home = os.path.join(BASE_DIR, "gradle_cache")
        java_temp_dir = os.path.join(BASE_DIR, "android_temp")
        custom_build_dir = os.path.join(BASE_DIR, "android_builds", nombre_paquete_limpio)
        for path in [gradle_user_home, java_temp_dir, custom_build_dir]:
            os.makedirs(path, exist_ok=True)
        safe_log(logbox, f"✓ Directorios de Gradle y build creados/verificados en: {BASE_DIR}")

        # --- 2. Modificar build.gradle de forma robusta ---
        android_gradle_path = os.path.join(ANDROID_DIR, "app", "build.gradle")
        if not os.path.exists(android_gradle_path):
            safe_log(logbox, f"✗ ERROR: build.gradle no encontrado en {android_gradle_path}")
            return False

        with open(android_gradle_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Filtrar cualquier línea 'buildDir' existente
        lines_sin_builddir = [line for line in lines if "buildDir" not in line]
        
        new_lines = []
        build_dir_inserted = False
        new_build_dir_line = f'    buildDir = file("{custom_build_dir.replace(os.sep, "/")}")\n'

        for line in lines_sin_builddir:
            new_lines.append(line)
            # Insertar la nueva línea de buildDir justo después de 'android {'
            if "android {" in line and not build_dir_inserted:
                new_lines.insert(len(new_lines), new_build_dir_line)
                build_dir_inserted = True
        
        if not build_dir_inserted:
            safe_log(logbox, f"✗ ERROR: No se encontró el bloque 'android {{' en build.gradle.")
            # Aún así, intentamos escribir el archivo por si acaso
            with open(android_gradle_path, 'w', encoding='utf-8') as f:
                f.writelines(lines_sin_builddir)
            return False

        with open(android_gradle_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        safe_log(logbox, f"✓ build.gradle actualizado para usar buildDir dinámico: {custom_build_dir}")

        # --- 3. Configurar variables de entorno y gradle.properties ---
        os.environ['GRADLE_USER_HOME'] = gradle_user_home
        os.environ['JAVA_OPTS'] = f'-Djava.io.tmpdir="{java_temp_dir}"'
        
        gradle_props_path = os.path.join(ANDROID_DIR, "gradle.properties")
        gradle_props_content = f"""
org.gradle.jvmargs=-Xmx4096m -XX:MaxMetaspaceSize=512m -Dfile.encoding=UTF-8
org.gradle.daemon=false
org.gradle.parallel=true
org.gradle.caching=true
android.useAndroidX=true
android.enableJetifier=true
"""
        with open(gradle_props_path, "w", encoding="utf-8") as f:
            f.write(gradle_props_content)
        safe_log(logbox, "✓ Archivo gradle.properties y variables de entorno configuradas.")
        
        return True
        
    except Exception as e:
        safe_log(logbox, f"✗ ERROR CRÍTICO configurando Gradle en disco F: {e}")
        import traceback
        safe_log(logbox, traceback.format_exc())
        return False

def compilar_apk_usando_disco_f(logbox, nombre_paquete_limpio):
    '''
    Versión del compilador que usa exclusivamente el disco F
    '''
    try:
        # 1. Configurar variables de entorno para usar disco F
        temp_base_dir = os.path.join(BASE_DIR, "temporal")
        os.environ['GRADLE_USER_HOME'] = os.path.join(temp_base_dir, "gradle")
        os.environ['JAVA_OPTS'] = f'-Duser.home={temp_base_dir} -Djava.io.tmpdir={os.path.join(temp_base_dir, "temp")}'
        os.environ['TEMP'] = os.path.join(temp_base_dir, "temp")
        os.environ['TMP'] = os.path.join(temp_base_dir, "temp")
        
        safe_log(logbox, f"✓ Variables de entorno configuradas para disco F")
        safe_log(logbox, f"  GRADLE_USER_HOME: {os.environ['GRADLE_USER_HOME']}")
        
        # 2. Verificar espacio una vez más
        disk_f = psutil.disk_usage('F:')
        free_gb_f = disk_f.free / (1024**3)
        safe_log(logbox, f"Espacio disponible en F: {free_gb_f:.1f} GB")
        
        if free_gb_f < 8:
            safe_log(logbox, f"⚠ ADVERTENCIA: Poco espacio en F: {free_gb_f:.1f} GB")
        
        # 3. Limpiar build anterior
        build_dir = os.path.join(ANDROID_DIR, "app", "build")
        if os.path.exists(build_dir):
            try:
                shutil.rmtree(build_dir)
                safe_log(logbox, "✓ Directorio build anterior limpiado")
            except Exception as e:
                safe_log(logbox, f"⚠ No se pudo limpiar build anterior: {e}")
        
        # 4. Configurar gradle.properties específico para disco F
        gradle_props_path = os.path.join(ANDROID_DIR, "gradle.properties")
        gradle_props_content = f'''# Configuración para usar disco F exclusivamente
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
        safe_log(logbox, "✓ gradle.properties actualizado para disco F")
        
        # 5. Intentar build con configuración de disco F
        max_intentos = 2
        for intento in range(1, max_intentos + 1):
            safe_log(logbox, f"=== INTENTO {intento}/{max_intentos} DE COMPILACIÓN USANDO DISCO F ===")
            
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
                
                # Build de APK usando disco F
                safe_log(logbox, "Iniciando compilación de APK usando disco F...")
                
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
                    safe_log(logbox, "✓ ¡APK COMPILADO EXITOSAMENTE USANDO DISCO F!")

                    safe_log(logbox, "✓ Build completado. Buscando el archivo APK generado...")

                    apk_origen = None

                    # Intentar primero en la ubicación personalizada (si se cambió el buildDir)
                    custom_build_dir = os.path.join(BASE_DIR, "android_builds", nombre_paquete_limpio)
                    apk_path_in_custom = os.path.join(custom_build_dir, "outputs", "apk", "debug", "app-debug.apk")
                    if os.path.exists(apk_path_in_custom):
                        apk_origen = apk_path_in_custom
                        safe_log(logbox, f"✓ APK encontrado en la ruta personalizada: {apk_origen}")
                    else:
                        # Intentar en la ubicación estándar (si no se cambió el buildDir)
                        standard_build_dir = os.path.join(ANDROID_DIR, "app", "build")
                        apk_path_in_standard = os.path.join(standard_build_dir, "outputs", "apk", "debug", "app-debug.apk")
                        if os.path.exists(apk_path_in_standard):
                            apk_origen = apk_path_in_standard
                            safe_log(logbox, f"✓ APK encontrado en la ruta estándar: {apk_origen}")
                        else:
                            # Si no se encuentra en las rutas conocidas, buscar recursivamente
                            safe_log(logbox, "APK no encontrado en rutas conocidas. Buscando recursivamente...")
                            search_dirs = [
                                custom_build_dir,
                                standard_build_dir
                            ]
                            for search_dir in search_dirs:
                                if not os.path.exists(search_dir):
                                    continue
                                safe_log(logbox, f"Buscando en: {search_dir}")
                                for root, dirs, files in os.walk(search_dir):
                                    if "app-debug.apk" in files:
                                        apk_origen = os.path.join(root, "app-debug.apk")
                                        safe_log(logbox, f"✓ APK encontrado en: {apk_origen}")
                                        break
                                if apk_origen:
                                    break

                    if apk_origen:
                        apk_dst_dir = os.path.join(OUTPUT_APK_DIR, nombre_paquete_limpio)
                        os.makedirs(apk_dst_dir, exist_ok=True)
                        apk_dst_file = os.path.join(apk_dst_dir, f"{nombre_paquete_limpio}.apk")

                        shutil.copy2(apk_origen, apk_dst_file)
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
                        safe_log(logbox, "✗ ERROR: Build reportó éxito, pero no se pudo encontrar el APK en los directorios de salida.")
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
        
        safe_log(logbox, "======== BUILD APK FALLIDO USANDO DISCO F ========")
        return None
        
    except Exception as e:
        safe_log(logbox, f"✗ ERROR CRÍTICO en compilar_apk_usando_disco_f: {e}")
        return None

def configurar_webview_camera_completo(logbox, android_dir_arg, package_name):
    
    java_base_dir = os.path.join(android_dir_arg, "app", "src", "main", "java")
    target_package_full_path = os.path.join(java_base_dir, *package_name.split('.'))
    os.makedirs(target_package_full_path, exist_ok=True)
    
    main_activity_content = f'''package {package_name};

import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{
    @Override
    public void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        
        // Configurar WebChromeClient para permisos de cámara y micrófono
        this.bridge.getWebView().setWebChromeClient(new WebChromeClient() {{
            @Override
            public void onPermissionRequest(final PermissionRequest request) {{
                runOnUiThread(() -> {{
                    String[] resources = request.getResources();
                    boolean hasCamera = false;
                    boolean hasMicrophone = false;
                    
                    for (String resource : resources) {{
                        if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)) {{
                            hasCamera = true;
                        }} else if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) {{
                            hasMicrophone = true;
                        }}
                    }}
                    
                    if (hasCamera || hasMicrophone) {{
                        // Conceder ambos permisos si se solicitan para simplificar
                        request.grant(request.getResources());
                    }} else {{
                        request.deny();
                    }}
                }});
            }}
        }});
    }}
}}'''
    
    main_activity_path = os.path.join(target_package_full_path, "MainActivity.java")
    with open(main_activity_path, "w", encoding="utf-8") as f:
        f.write(main_activity_content)
    safe_log(logbox, f"✓ MainActivity.java (con WebChromeClient) configurado en: {main_activity_path}")


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
    Prepara el proyecto Capacitor en el directorio de trabajo, preservando
    las plataformas nativas (como 'android') si ya existen.
    Copia los archivos de la plantilla web y de configuración, asegurando un
    estado limpio para el build sin destruir el proyecto nativo.
    """
    capacitor_dir = PROJECT_DIR
    template_dir = CAPACITOR_TEMPLATE
    safe_log(logbox, f"Preparando proyecto Capacitor en: {capacitor_dir}")

    # Asegurarse de que el directorio de trabajo exista
    os.makedirs(capacitor_dir, exist_ok=True)

    safe_log(logbox, "Refrescando proyecto desde la plantilla...")
    # Iterar sobre los contenidos de la plantilla para copiarlos
    for item in os.listdir(template_dir):
        template_item_path = os.path.join(template_dir, item)
        project_item_path = os.path.join(capacitor_dir, item)

        # No tocar las carpetas de plataformas nativas ni node_modules
        if item in ['android', 'ios', 'node_modules']:
            safe_log(logbox, f"  - Omitiendo '{item}' para preservar la plataforma nativa/dependencias.")
            continue

        # Si el item existe en el proyecto, lo borramos para asegurar una copia limpia
        if os.path.exists(project_item_path):
            if os.path.isdir(project_item_path):
                shutil.rmtree(project_item_path)
            else:
                os.remove(project_item_path)

        # Copiamos el item desde la plantilla al proyecto
        if os.path.isdir(template_item_path):
            shutil.copytree(template_item_path, project_item_path)
        else:
            shutil.copy2(template_item_path, project_item_path)
    safe_log(logbox, "✓ Proyecto refrescado desde la plantilla preservando plataformas.")

    # Asegurarse de que las carpetas mipmap existan en el proyecto de trabajo después de la copia.
    # Esto es importante para la generación de íconos.
    mipmap_folders = [
        os.path.join(ICONO_BASE_DIR, "mipmap-mdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-hdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-xhdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-xxhdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-xxxhdpi"),
        os.path.join(ICONO_BASE_DIR, "mipmap-anydpi-v26"),
    ]
    # Esta parte asume que ANDROID_DIR existe. Si no existe, fallará.
    # El flujo de trabajo implica que el usuario ejecute `npx cap add android` en algún momento,
    # lo cual crea el directorio 'android'. Nuestra función ahora lo preserva.
    if os.path.exists(ANDROID_DIR):
        for folder in mipmap_folders:
            os.makedirs(folder, exist_ok=True)
        safe_log(logbox, "✓ Carpetas mipmap en proyecto de trabajo verificadas/creadas.")
    else:
        safe_log(logbox, "ADVERTENCIA: El directorio 'android' no existe. La creación de carpetas mipmap se omitirá. Ejecute 'npx cap add android' en el directorio del proyecto.")

def instalar_arjs_y_limpiar(logbox):
    project_dir = PROJECT_DIR
    try:
        safe_log(logbox, f"Cambiando al directorio del proyecto: {project_dir}")
        
        safe_log(logbox, "Limpiando cache npm...")
        subprocess.run(["npm", "cache", "clean", "--force"], check=True, cwd=project_dir, shell=True)

        node_modules_path = os.path.join(project_dir, "node_modules")
        if os.path.exists(node_modules_path):
            safe_log(logbox, "Eliminando carpeta node_modules para instalación limpia...")
            shutil.rmtree(node_modules_path)
        else:
            safe_log(logbox, "No existe carpeta node_modules, se omite eliminación.")

        safe_log(logbox, "Instalando @ar-js-org/ar.js versión 3.4.7...")
        subprocess.run(["npm", "install", "@ar-js-org/ar.js@3.4.7", "--save"], check=True, cwd=project_dir, shell=True)

        safe_log(logbox, "Instalación de AR.js completada correctamente.")
        return True

    except subprocess.CalledProcessError as e:
        safe_log(logbox, f"ERROR en instalación de AR.js: {e}")
        messagebox.showerror("Error de Dependencias", f"Falla en la instalación de AR.js: {e}")
        return False
    except Exception as e:
        safe_log(logbox, f"ERROR inesperado durante instalación de AR.js: {e}")
        messagebox.showerror("Error de Dependencias", f"Falla inesperada durante la instalación de AR.js: {e}")
        return False

def verificar_instalacion_arjs(logbox):
    project_dir = PROJECT_DIR
    try:
        result = subprocess.run(
            ["npm", "list", "@ar-js-org/ar.js", "--depth=0"],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_dir,
            shell=True
        )
        output = result.stdout
        if "@ar-js-org/ar.js@3.4.7" in output:
            safe_log(logbox, "✓ Verificación exitosa: AR.js versión 3.4.7 está instalada.")
            return True
        else:
            safe_log(logbox, "AR.js no está instalado en la versión correcta. Se necesita v3.4.7.")
            return False
    except subprocess.CalledProcessError:
        safe_log(logbox, "No se encontró AR.js instalado.")
        return False
    except Exception as e:
        safe_log(logbox, f"ERROR verificando instalación de AR.js: {e}")
        return False


def crear_styles_xml(logbox):
    """Crea el archivo styles.xml con el tema SplashScreen necesario"""
    values_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "values")
    os.makedirs(values_dir, exist_ok=True)
    
    styles_content = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Base application theme. -->
    <style name="AppTheme" parent="Theme.AppCompat.Light.DarkActionBar">
        <item name="colorPrimary">@color/colorPrimary</item>
        <item name="colorPrimaryDark">@color/colorPrimaryDark</item>
        <item name="colorAccent">@color/colorAccent</item>
    </style>

    <!-- Theme para SplashScreen -->
    <style name="Theme.SplashScreen" parent="Theme.AppCompat.NoActionBar">
        <item name="android:windowBackground">@drawable/splash_background</item>
        <item name="android:windowFullscreen">true</item>
        <item name="android:windowContentOverlay">@null</item>
    </style>
</resources>"""
    
    styles_path = os.path.join(values_dir, "styles.xml")
    with open(styles_path, "w", encoding="utf-8") as f:
        f.write(styles_content)
    safe_log(logbox, f"✓ styles.xml creado en: {styles_path}")

def crear_colors_xml(logbox):
    """Crea el archivo colors.xml con colores básicos"""
    values_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "values")
    os.makedirs(values_dir, exist_ok=True)
    
    colors_content = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="colorPrimary">#3F51B5</color>
    <color name="colorPrimaryDark">#303F9F</color>
    <color name="colorAccent">#FF4081</color>
    <color name="splash_background">#FFFFFF</color>
</resources>"""
    
    colors_path = os.path.join(values_dir, "colors.xml")
    with open(colors_path, "w", encoding="utf-8") as f:
        f.write(colors_content)
    safe_log(logbox, f"✓ colors.xml creado en: {colors_path}")

def crear_splash_background(logbox):
    """Crea el drawable para el fondo del SplashScreen"""
    drawable_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "drawable")
    os.makedirs(drawable_dir, exist_ok=True)
    
    splash_content = """<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:drawable="@color/splash_background" />
    <item>
        <bitmap
            android:gravity="center"
            android:src="@mipmap/ic_launcher" />
    </item>
</layer-list>"""
    
    splash_path = os.path.join(drawable_dir, "splash_background.xml")
    with open(splash_path, "w", encoding="utf-8") as f:
        f.write(splash_content)
    safe_log(logbox, f"✓ splash_background.xml creado en: {splash_path}")

def instalar_o_actualizar_arjs_si_necesario(logbox):
    """
    Verifica si @ar-js-org/ar.js@3.4.7 está instalado.
    Si no está, instala limpiando antes.
    Retorna True si todo está OK, False si falla.
    """
    safe_log(logbox, "Verificando instalación de dependencias de AR.js...")
    if verificar_instalacion_arjs(logbox):
        return True
    else:
        safe_log(logbox, "La dependencia AR.js no está instalada o la versión es incorrecta. Iniciando instalación...")
        return instalar_arjs_y_limpiar(logbox)


def limpiar_y_regenerar_android(logbox):
    """
    Elimina por completo el directorio 'android' y lo regenera con 'npx cap add android'.
    Esta es una medida drástica para asegurar que no queden configuraciones cacheadas.
    """
    safe_log(logbox, "--- INICIANDO LIMPIEZA Y REGENERACIÓN AGRESIVA DEL PROYECTO ANDROID ---")
    if os.path.exists(ANDROID_DIR):
        safe_log(logbox, f"Eliminando el directorio Android existente en: {ANDROID_DIR}")
        try:
            shutil.rmtree(ANDROID_DIR)
            safe_log(logbox, "✓ Directorio Android eliminado exitosamente.")
        except Exception as e:
            safe_log(logbox, f"✗ ERROR CRÍTICO al eliminar el directorio Android: {e}")
            messagebox.showerror(
                "Error de Limpieza",
                f"No se pudo eliminar la carpeta 'android'.\n"
                f"Cierra Android Studio o cualquier explorador de archivos que la esté usando y reintenta.\n\nError: {e}"
            )
            return False  # Detener el proceso si la eliminación falla

    safe_log(logbox, "Regenerando el proyecto Android con 'npx cap add android'...")
    try:
        # Usar subprocess.run para capturar la salida y manejar errores
        result = subprocess.run(
            ["npx", "cap", "add", "android"],
            cwd=PROJECT_DIR,
            check=True,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        safe_log(logbox, "✓ Proyecto Android regenerado exitosamente.")
        safe_log(logbox, f"Salida de Capacitor:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        safe_log(logbox, f"✗ ERROR CRÍTICO: 'npx cap add android' falló.")
        safe_log(logbox, f"  Código de Salida: {e.returncode}")
        safe_log(logbox, f"  Salida de Error (stderr):\n{e.stderr}")
        safe_log(logbox, f"  Salida Estándar (stdout):\n{e.stdout}")
        messagebox.showerror(
            "Error de Capacitor",
            f"No se pudo regenerar el proyecto Android.\n\n"
            f"Error: {e.stderr}"
        )
        return False
    except Exception as e:
        safe_log(logbox, f"✗ Ocurrió un error inesperado al regenerar el proyecto Android: {e}")
        return False


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

        Button(log_frame, text="Copiar Log", command=self.copy_log_to_clipboard).pack(pady=5)

        self.label_progreso = Label(self.root, text="Listo.", relief="sunken", anchor="w", padx=5)
        self.label_progreso.pack(side="bottom", fill="x")

    def set_progress(self, text, color="black"):
        """Actualiza el texto y color de la barra de progreso en la GUI."""
        self.label_progreso.config(text=text, fg=color)
        self.root.update_idletasks() # Forzar actualización de la GUI

    def copy_log_to_clipboard(self):
        """Copia todo el contenido del log al portapapeles."""
        try:
            log_text = self.logbox.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(log_text)
            self.set_progress("Log copiado al portapapeles.", "green")
            safe_log(self.logbox, "✓ Log copiado al portapapeles.")
        except Exception as e:
            self.set_progress("Error al copiar el log.", "red")
            safe_log(self.logbox, f"✗ Error al copiar log: {e}")

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
            www_data_dir = os.path.join(WWW_DIR, "data")
            os.makedirs(www_models_dir, exist_ok=True)
            os.makedirs(www_patterns_dir, exist_ok=True)
            os.makedirs(www_data_dir, exist_ok=True)
            
            # Asegurar que el archivo camera_para.dat exista, descargándolo si es necesario.
            if not ensure_camera_para_dat(self.logbox, www_data_dir):
                # La función `ensure_camera_para_dat` ya muestra un messagebox de error.
                # Detener la generación del paquete es lo correcto si el archivo es crítico.
                return False


            ar_content_list = []
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

                    # --- Lógica de Generación de Marcadores Simplificada (Solo .patt) ---
                    nombre_limpio = par['base']
                    marker_type = 'pattern' # El nuevo frontend está diseñado para 'pattern'
                    
                    # Generar patrón .patt con OpenCV
                    patt_dest_www = os.path.join(www_patterns_dir, f"{nombre_limpio}.patt")
                    if generar_patt_opencv(self.logbox, img_dest_paquete, patt_dest_www):
                        marker_url = os.path.join("patterns", f"{nombre_limpio}.patt").replace("\\", "/")
                        model_url = os.path.join("models", f"{nombre_limpio}.glb").replace("\\", "/")
                        
                        ar_content_list.append({
                            "type": marker_type,
                            "markerUrl": marker_url,
                            "modelUrl": model_url
                        })
                        safe_log(self.logbox, f"✓ Marcador '{marker_type}' procesado para: {nombre_limpio}")
                    else:
                        safe_log(self.logbox, f"✗ ERROR: Falló la generación del marcador .patt para {nombre_limpio}.")


            # 2. Generar y guardar claves
            self.claves = [self._generar_codigo_eco() for _ in range(cantidad)]
            insertar_claves_en_backend(self.logbox, self.claves)
            claves_file = os.path.join(OUTPUT_APK_DIR, f"{nombre}_claves.txt")
            with open(claves_file, "w", encoding="utf-8") as f: f.write("\n".join(self.claves))
            safe_log(self.logbox, f"✓ {cantidad} claves generadas.")

            # 3. Generar y guardar los 4 archivos HTML (incluyendo la nueva vista web)
            activation_html = self.generate_activation_html(nombre, backend_url)
            main_menu_html = self.generate_main_menu_html(nombre)
            ar_viewer_html = self.generate_ar_viewer_html(nombre, ar_content_list)
            web_ar_viewer_html = self.generate_web_ar_viewer_html(nombre, ar_content_list)

            for filename, content in [
                ("index.html", activation_html),
                ("main-menu.html", main_menu_html),
                ("ar-viewer.html", ar_viewer_html),
                ("web-ar-viewer.html", web_ar_viewer_html)
            ]:
                with open(os.path.join(WWW_DIR, filename), "w", encoding="utf-8") as f:
                    f.write(content)
                with open(os.path.join(paquete_dir, filename), "w", encoding="utf-8") as f:
                    f.write(content)
                safe_log(self.logbox, f"✓ Archivo HTML generado y guardado: {filename}")

            # Crear ambos archivos frontend-ar
            self.crear_y_copiar_frontend_ar(self.logbox)
            self.crear_y_copiar_web_frontend_ar(self.logbox)

            # 4. Actualizar config de Capacitor
            package_name = get_package_name(nombre)
            config_path = os.path.join(PROJECT_DIR, "capacitor.config.json")
            capacitor_config = {
                "appId": package_name,
                "appName": self.nombre_libro.get().strip(),
                "webDir": "www",
                "backgroundColor": "#00000000",
                "bundledWebRuntime": False,
                "android": {
                    "allowMixedContent": True,
                    "webSecurity": False,
                    "appendUserAgent": "ARCapacitorApp/1.0"
                },
                "server": {
                    "hostname": "localhost",
                    "androidScheme": "http",
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
        <button id="activateBtn" class="activate-btn" onclick="validateCode()">Activar</button>
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
            const activateBtn = document.getElementById('activateBtn');
            const code = document.getElementById('activationCode').value.trim().toUpperCase();
            const messageDiv = document.getElementById('message');
            
            if (activateBtn.disabled) return;

            activateBtn.disabled = true;
            activateBtn.innerText = 'Validando...';
            messageDiv.innerHTML = '';

            if (!code) {{
                messageDiv.innerHTML = '<p class="error">Por favor ingresa un código</p>';
                activateBtn.disabled = false;
                activateBtn.innerText = 'Activar';
                return;
            }}

            try {{
                const deviceId = await getOrCreateDeviceId();
                const payload = {{ token: code, device_id: deviceId }};
                
                const response = await fetch('{activation_url}', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload),
                    // Agregamos un timeout a la petición fetch
                    signal: AbortSignal.timeout(15000) // 15 segundos
                }});

                if (!response.ok) {{
                    throw new Error(`Error HTTP: ${{response.status}}`);
                }}
                
                const result = await response.json();

                if (result.valid) {{
                    messageDiv.innerHTML = '<p class="success">¡Código válido! Redirigiendo...</p>';
                    localStorage.setItem('app_activated', 'true');
                    localStorage.setItem('activation_code', code);
                    setTimeout(() => {{ window.location.href = 'main-menu.html'; }}, 1500);
                }} else {{
                    messageDiv.innerHTML = `<p class="error">${{result.error || 'Código inválido o ya utilizado.'}}</p>`;
                    activateBtn.disabled = false;
                    activateBtn.innerText = 'Activar';
                }}
            }} catch (error) {{
                messageDiv.innerHTML = '<p class="error">Error de conexión o el servidor tardó en responder. Verifica tu internet.</p>';
                console.error('Error de activación:', error);
                activateBtn.disabled = false;
                activateBtn.innerText = 'Activar';
            }}
        }}
    </script>
</body>
</html>"""

    def generate_main_menu_html(self, nombre):
        explicacion_btn_html = f'<button class="menu-btn explanation-btn" onclick="openExplanation()">💡 Explicación</button>' if self.explicacion_var.get().strip() else ''
        open_explanation_js = f"function openExplanation() {{ window.open('{self.explicacion_var.get().strip()}', '_blank'); }}" if self.explicacion_var.get().strip() else 'function openExplanation() {}'

        # Nuevo botón para vista previa web
        web_ar_btn = '<button class="menu-btn web-ar-btn" onclick="startWebAR()">🌐 Vista Previa AR (Web)</button>'

        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{nombre} - Menú Principal</title>
<script src="capacitor.js"></script>
<style>
body {{ font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
.menu-container {{ background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); text-align: center; max-width: 400px; width: 90%; overflow-y: auto; max-height: 90vh;}}
.logo {{ width: 100px; height: 100px; margin: 0 auto 1rem; background: url('portada.jpg') center/cover; border-radius: 50%; }}
.menu-btn {{ width: 100%; padding: 1.2rem; margin: 0.8rem 0; border: none; border-radius: 8px; font-size: 1.1rem; cursor: pointer; transition: background 0.3s, transform 0.2s; }}
.menu-btn:hover {{ transform: translateY(-2px); }}
.video-btn {{ background: #2196F3; color: white; }}
.explanation-btn {{ background: #FF9800; color: white; }}
.ar-btn {{ background: #4CAF50; color: white; font-weight: bold; }}
.web-ar-btn {{ background: #9C27B0; color: white; font-weight: bold; }}
.ar-btn:hover {{ background: #45a049; }}
.web-ar-btn:hover {{ background: #7B1FA2; }}
</style>
</head>
<body>
<div class="menu-container">
<div class="logo"></div>
<h1 style="color: #333;">{nombre}</h1>
<p style="margin-bottom: 2rem; color: #666;">Selecciona una opción</p>
{web_ar_btn}
<button class="menu-btn ar-btn" onclick="startAR()">📱 Iniciar Realidad Aumentada (APK)</button>
<button class="menu-btn video-btn" onclick="openVideo()">📢 Ver Video Promocional</button>
{explicacion_btn_html}
</div>
<script>
function openVideo() {{ window.open('{self.propaganda_var.get().strip()}', '_blank'); }}
{open_explanation_js}

function startWebAR() {{
// Redirigir a la vista web de AR
window.location.href = 'web-ar-viewer.html';
}}

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

    def generate_ar_viewer_html(self, nombre, ar_content_list):
        # Convertir la lista de diccionarios de Python a una cadena JSON
        ar_content_json = json.dumps(ar_content_list)

        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Visor AR - {nombre}</title>
    <style>
        html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background-color: black; }}
        canvas {{ display: block; }}
        #backBtn {{
            position: fixed; top: 10px; left: 10px; z-index: 999;
            font-size: 18px; padding: 8px 12px; background: rgba(0,0,0,0.6);
            color: white; border: none; border-radius: 5px; cursor: pointer;
        }}
    </style>
</head>
<body>
    <button id="backBtn" onclick="window.location.href='main-menu.html'">Volver al Menú</button>

    <!-- Inyectar el contenido AR como una variable global de JavaScript -->
    <script>
        window.arContent = {ar_content_json};
    </script>

    <!-- Scripts requeridos para la nueva implementación de AR -->
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
    <script src="https://cdn.jsdelivr.net/gh/AR-js-org/AR.js@3.4.7/three.js/build/ar-threex.js"></script>

    <!-- El script principal que contiene la lógica de AR -->
    <script src="js/frontend-ar.js"></script>
</body>
</html>"""

    def generate_web_ar_viewer_html(self, nombre, ar_content_list):
        ar_content_json = json.dumps(ar_content_list)

        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Vista Previa AR - {nombre}</title>
<style>
html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background-color: black; }}
canvas {{ display: block; }}
#backBtn, #infoBtn {{
position: fixed; z-index: 999;
font-size: 18px; padding: 8px 12px; background: rgba(0,0,0,0.6);
color: white; border: none; border-radius: 5px; cursor: pointer;
}}
#backBtn {{ top: 10px; left: 10px; }}
#infoBtn {{ top: 10px; right: 10px; }}
#infoPanel {{
position: fixed; top: 60px; right: 10px; width: 300px;
background: rgba(0,0,0,0.8); color: white; padding: 15px;
border-radius: 10px; display: none; z-index: 998;
}}
.marker-info {{
margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #555;
}}
.marker-info:last-child {{ border-bottom: none; margin-bottom: 0; }}
</style>
</head>
<body>
<button id="backBtn" onclick="window.location.href='main-menu.html'">Volver al Menú</button>
<button id="infoBtn" onclick="toggleInfo()">ℹ️ Info</button>

<div id="infoPanel">
<h3>Instrucciones de uso:</h3>
<ol>
<li>Permite acceso a la cámara cuando se solicite</li>
<li>Imprime los marcadores disponibles</li>
<li>Muestra cada marcador frente a la cámara</li>
<li>El modelo 3D aparecerá sobre el marcador</li>
</ol>
<h3>Marcadores disponibles:</h3>
<div id="markersList"></div>
</div>

<script>
window.arContent = {ar_content_json};
</script>

<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
<script src="https://cdn.jsdelivr.net/gh/AR-js-org/AR.js@3.4.7/three.js/build/ar-threex.js"></script>
<script src="js/web-frontend-ar.js"></script>
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

    def crear_y_copiar_frontend_ar(self, logbox):
        """
        Crea el archivo frontend-ar.js con una lógica simplificada y robusta que
        delega el manejo de la cámara directamente a AR.js.
        """
        frontend_ar_code = """
// frontend-ar.js - Versión simplificada con sourceType: 'webcam'
document.addEventListener('DOMContentLoaded', () => {
    console.log("Entorno AR cargado. Inicializando AR.js...");
    initializeAR();
});

function initializeAR() {
    const scene = new THREE.Scene();
    const camera = new THREE.Camera();
    scene.add(camera);

    const renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true
    });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.domElement.style.position = 'fixed';
    renderer.domElement.style.top = '0';
    renderer.domElement.style.left = '0';
    document.body.appendChild(renderer.domElement);

    // Inicializar AR.js delegando el control de la cámara
    const arToolkitSource = new THREEx.ArToolkitSource({
        sourceType: 'webcam',
        sourceWidth: window.innerWidth,
        sourceHeight: window.innerHeight,
    });

    arToolkitSource.init(() => {
        // Redimensionar el video para que ocupe toda la pantalla
        arToolkitSource.domElement.style.position = 'fixed';
        arToolkitSource.domElement.style.top = '0';
        arToolkitSource.domElement.style.left = '0';
        arToolkitSource.domElement.style.zIndex = '-1';
        arToolkitSource.onResizeElement();
        arToolkitSource.copyElementSizeTo(renderer.domElement);
        
        console.log("ARToolkitSource inicializado correctamente.");

        const arToolkitContext = new THREEx.ArToolkitContext({
            cameraParametersUrl: 'data/camera_para.dat',
            detectionMode: 'mono',
            maxDetectionRate: 30
        });

        arToolkitContext.init(() => {
            console.log("ARToolkitContext inicializado correctamente.");
            camera.projectionMatrix.copy(arToolkitContext.getProjectionMatrix());

            if (window.arContent && Array.isArray(window.arContent)) {
                window.arContent.forEach(content => {
                    createMarker(content, scene, arToolkitContext);
                });
            } else {
                console.error("No se encontró contenido AR. Verifica window.arContent");
            }
            animate();
        });
    });

    function animate() {
        requestAnimationFrame(animate);
        if (arToolkitSource.ready === false) return;
        arToolkitContext.update(arToolkitSource.domElement);
        renderer.render(scene, camera);
    }

    function createMarker(content, scene, arToolkitContext) {
        const markerRoot = new THREE.Group();
        scene.add(markerRoot);

        new THREEx.ArMarkerControls(arToolkitContext, markerRoot, {
            type: 'pattern',
            patternUrl: content.markerUrl,
            changeMatrixMode: 'cameraTransformMatrix'
        });

        const loader = new THREE.GLTFLoader();
        loader.load(content.modelUrl, (gltf) => {
            const model = gltf.scene;
            const box = new THREE.Box3().setFromObject(model);
            const size = box.getSize(new THREE.Vector3());
            const scale = 0.8 / Math.max(size.x, size.y, size.z);
            model.scale.set(scale, scale, scale);
            const center = box.getCenter(new THREE.Vector3());
            model.position.sub(center);
            markerRoot.add(model);
        });
    }
}
"""
        src_path = os.path.join(GEN_DIR, "frontend-ar.js")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(frontend_ar_code)
        
        destino_js_dir = os.path.join(WWW_DIR, "js")
        os.makedirs(destino_js_dir, exist_ok=True)
        shutil.copy2(src_path, destino_js_dir)
        safe_log(self.logbox, f"✓ frontend-ar.js (versión simplificada) creado y copiado a {destino_js_dir}")

    def crear_y_copiar_web_frontend_ar(self, logbox):
        web_frontend_ar_code = """
// web-frontend-ar.js - Versión para vista web previa
document.addEventListener('DOMContentLoaded', () => {
console.log("Vista Web AR cargada. Inicializando AR.js...");
initializeWebAR();
populateMarkersList();
});

function populateMarkersList() {
const markersList = document.getElementById('markersList');
if (!markersList || !window.arContent) return;

markersList.innerHTML = '';
window.arContent.forEach((content, index) => {
const markerInfo = document.createElement('div');
markerInfo.className = 'marker-info';
markerInfo.innerHTML = `
<strong>Marcador ${index + 1}:</strong><br>
Modelo: ${content.modelUrl.split('/').pop()}
`;
markersList.appendChild(markerInfo);
});
}

function toggleInfo() {
const infoPanel = document.getElementById('infoPanel');
infoPanel.style.display = infoPanel.style.display === 'none' ? 'block' : 'none';
}

function initializeWebAR() {
const scene = new THREE.Scene();
const camera = new THREE.Camera();
scene.add(camera);

const renderer = new THREE.WebGLRenderer({
antialias: true,
alpha: true
});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.domElement.style.position = 'fixed';
renderer.domElement.style.top = '0';
renderer.domElement.style.left = '0';
document.body.appendChild(renderer.domElement);

// Inicializar AR.js para web
const arToolkitSource = new THREEx.ArToolkitSource({
sourceType: 'webcam',
sourceWidth: window.innerWidth,
sourceHeight: window.innerHeight,
});

arToolkitSource.init(() => {
console.log("ARToolkitSource inicializado correctamente para web.");

const arToolkitContext = new THREEx.ArToolkitContext({
cameraParametersUrl: 'data/camera_para.dat',
detectionMode: 'mono',
maxDetectionRate: 30
});

arToolkitContext.init(() => {
console.log("ARToolkitContext inicializado correctamente para web.");
camera.projectionMatrix.copy(arToolkitContext.getProjectionMatrix());

if (window.arContent && Array.isArray(window.arContent)) {
window.arContent.forEach(content => {
createMarker(content, scene, arToolkitContext);
});
} else {
console.error("No se encontró contenido AR. Verifica window.arContent");
}
animate();
});
});

function animate() {
requestAnimationFrame(animate);
if (arToolkitSource.ready === false) return;
arToolkitContext.update(arToolkitSource.domElement);
renderer.render(scene, camera);
}

function createMarker(content, scene, arToolkitContext) {
const markerRoot = new THREE.Group();
scene.add(markerRoot);

new THREEx.ArMarkerControls(arToolkitContext, markerRoot, {
type: 'pattern',
patternUrl: content.markerUrl,
changeMatrixMode: 'cameraTransformMatrix'
});

const loader = new THREE.GLTFLoader();
loader.load(content.modelUrl, (gltf) => {
const model = gltf.scene;
const box = new THREE.Box3().setFromObject(model);
const size = box.getSize(new THREE.Vector3());
const scale = 0.8 / Math.max(size.x, size.y, size.z);
model.scale.set(scale, scale, scale);
const center = box.getCenter(new THREE.Vector3());
model.position.sub(center);
markerRoot.add(model);

console.log(`Modelo cargado: ${content.modelUrl}`);
}, undefined, (error) => {
console.error(`Error cargando modelo ${content.modelUrl}:`, error);
});
}
}
"""
        src_path = os.path.join(GEN_DIR, "web-frontend-ar.js")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(web_frontend_ar_code)

        destino_js_dir = os.path.join(WWW_DIR, "js")
        os.makedirs(destino_js_dir, exist_ok=True)
        shutil.copy2(src_path, destino_js_dir)
        safe_log(self.logbox, f"✓ web-frontend-ar.js creado y copiado a {destino_js_dir}")

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
            
            # Llama a corrige_android_manifest con el nombre del paquete unificado
            nombre_limpio = limpiar_nombre(self.nombre_libro.get().strip())
            package_name = get_package_name(nombre_limpio)
            corregir_android_manifest(self.logbox, package_name)
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
        safe_log(self.logbox, "--- INICIANDO PROCESO DE GENERACIÓN DE APK ---")
        nombre = limpiar_nombre(self.nombre_libro.get().strip())
        if not nombre:
            messagebox.showerror("Error", "El nombre del paquete está vacío.")
            return

        # --- Limpieza y Regeneración del Proyecto Android ---
        if not limpiar_y_regenerar_android(self.logbox):
            self.set_progress("Error regenerando proyecto Android.", "red")
            return

        # --- Generar el build.gradle raíz para estabilizar el entorno ---
        if not generar_root_build_gradle(self.logbox):
            self.set_progress("Error generando el build.gradle raíz.", "red")
            return

        # 1. Preparar el proyecto limpio desde la plantilla ANTES de cualquier otra cosa.
        preparar_proyecto_capacitor(self.logbox)

        # 2. Realizar el resto de las operaciones sobre el proyecto ya copiado y configurado.
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
        
        # Crear recursos de estilo para evitar errores de compilación de tema
        crear_styles_xml(self.logbox)
        crear_colors_xml(self.logbox)
        crear_splash_background(self.logbox)

        try:
            # --- LÓGICA UNIFICADA Y DEFINITIVA PARA CONFIGURAR PAQUETE ---
            package_name = get_package_name(nombre)
            app_name = self.nombre_libro.get().strip()
            safe_log(self.logbox, f"✓ Usando packageName unificado: {package_name}")

            # 1. Crear MainActivity.java (que ahora incluye toda la lógica de permisos)
            crear_main_activity(self.logbox, package_name)

            # 2. Actualizar capacitor.config.json
            actualizar_capacitor_config(self.logbox, package_name, app_name)
            
            # 3. Generar un build.gradle completo y robusto
            if not generar_build_gradle_completo(self.logbox, package_name):
                messagebox.showerror("Error Crítico", "No se pudo generar el archivo build.gradle. La compilación fallará.")
                self.set_progress("Error configurando build.gradle.", "red")
                return

            # 4. Sobrescribir AndroidManifest con una plantilla limpia y válida
            # La llamada a corregir_android_manifest en generar_iconos ya se encarga de esto.
            # No es necesario llamarlo aquí de nuevo.
            # corregir_android_manifest(self.logbox, package_name)

            # 5. Lógica restante de configuración
            backend_url_gui = self.backend_url.get().strip()
            backend_host = re.search(r'https?://([^:/]+)', backend_url_gui).group(1) if re.search(r'https?://([^:/]+)', backend_url_gui) else None
            crear_archivos_adicionales_android(self.logbox, backend_host)
            self.generar_iconos()
            self.crear_y_copiar_frontend_ar(self.logbox) # Crear e inyectar el script de AR
            
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
            # --- Verificación e instalación de dependencias ---
            if not instalar_o_actualizar_arjs_si_necesario(self.logbox):
                self.set_progress("Error de dependencias de AR.js.", "red")
                messagebox.showerror("Error", "No se pudo instalar/verificar la dependencia de AR.js. Revisa el log.")
                return

            # --- LIMPIEZA PROFUNDA ---
            dirs_a_borrar = [
                os.path.join(ANDROID_DIR, "app", "build"),
                os.path.join(ANDROID_DIR, "build"),
                os.path.join(ANDROID_DIR, ".gradle")
            ]
            for d in dirs_a_borrar:
                if os.path.exists(d):
                    try:
                        shutil.rmtree(d)
                    except Exception as e:
                        safe_log(self.logbox, f"ADVERTENCIA: No se pudo borrar {d}: {e}")
            safe_log(self.logbox, "✓ Limpieza profunda de carpetas de build y caché de Gradle completada.")

            safe_log(self.logbox, "Ejecutando 'npm install'...")
            subprocess.run("npm install", cwd=PROJECT_DIR, check=True, shell=True, capture_output=True, text=True)
            safe_log(self.logbox, "✓ Dependencias de npm instaladas.")

            safe_log(self.logbox, "Instalando plugin de cámara de Capacitor...")
            try:
                subprocess.run(["npm", "install", "@capacitor/camera"], cwd=PROJECT_DIR, check=True, shell=True, capture_output=True, text=True)
                safe_log(self.logbox, "✓ Plugin de cámara de Capacitor instalado.")
            except Exception as e:
                safe_log(self.logbox, f"✗ ERROR instalando el plugin de cámara: {e}")
                messagebox.showerror("Error de Plugin", f"No se pudo instalar @capacitor/camera: {e}")
                return # Stop the build

            # Asegurarse de que capacitor.js esté presente en www/
            ensure_capacitor_js(self.logbox, PROJECT_DIR)
            
            # Usar la nueva función para compilar usando el disco F
            apk_path = compilar_apk_usando_disco_f(self.logbox, nombre_paquete_limpio)

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

                # Abrir la carpeta de salida automáticamente
                try:
                    safe_log(self.logbox, f"Abriendo la carpeta de salida: {final_apk_dest_dir}")
                    os.startfile(final_apk_dest_dir)
                except Exception as e:
                    safe_log(self.logbox, f"✗ No se pudo abrir la carpeta de salida automáticamente: {e}")
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
        # Define a simple Flask app to serve the 'www' directory
        app = Flask(__name__)
        CORS(app) # Habilitar CORS para todas las rutas

        @app.route('/<path:path>')
        def serve_static(path):
            if not os.path.exists(WWW_DIR):
                return "El directorio 'www' no ha sido generado todavía.", 404
            return send_from_directory(WWW_DIR, path)

        @app.route('/')
        def serve_index():
            index_path = os.path.join(WWW_DIR, 'index.html')
            if not os.path.exists(index_path):
                return "index.html no encontrado. Por favor, genere el paquete primero.", 404
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
            # Primero, desconectar cualquier túnel existente para evitar el error de sesión múltiple.
            for tunnel in ngrok.get_tunnels():
                ngrok.disconnect(tunnel.public_url)
                safe_log(self.logbox, f"✓ Túnel ngrok anterior desconectado: {tunnel.public_url}")
            
            # Ahora, conectar un nuevo túnel
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


