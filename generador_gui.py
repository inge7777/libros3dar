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
from visor3d_webview import lanzar_visor_3d

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

# =========================
# CONFIGURACIÓN DE ENTORNO CENTRALIZADA
# =========================
import os
from core.env import get_paths, validate_env
from core.capacitor import ensure_capacitor_app
from core.ar_frontend import write_frontend
from core.apk_build import build_debug_apk
from core.utils import limpiar_nombre
from core.log import safe_log, mostrar_log
from core.imaging3d.single_image import generate_single_image_model
from core.imaging3d.multiview import generate_multiview_model

# Cargar todas las rutas como variables globales para que el resto del script funcione sin cambios
globals().update(get_paths())

# Crear directorios de salida que antes se creaban bajo las constantes
os.makedirs(OUTPUT_3DMODELS_DIR, exist_ok=True)
os.makedirs(MODELS_SHARED_DIR, exist_ok=True)


# -------------- FUNCIONES AUXILIARES --------------

# La función limpiar_nombre ha sido movida a core/utils.py

def get_package_name(nombre_limpio: str) -> str:
    """Genera el nombre del paquete de Android."""
    return f"com.librosdar.{nombre_limpio}"

def preparar_rutas_java(package_name):
    java_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "java", *package_name.split('.'))
    os.makedirs(java_dir, exist_ok=True)
    return os.path.join(java_dir, "MainActivity.java")

def crear_main_activity(package_name):
    ruta = preparar_rutas_java(package_name)
    codigo = f"""package {package_name};

import android.os.Bundle;
import android.widget.Toast;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{

    @Override
    public void onResume() {{
        super.onResume();
        // Verificar y solicitar permisos de cámara al reanudar la actividad.
        // Esto es crucial para la funcionalidad de AR.
        if (!CameraPermissionHelper.hasCameraPermission(this)) {{
            CameraPermissionHelper.requestCameraPermission(this);
        }}
    }}

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {{
        super.onRequestPermissionsResult(requestCode, permissions, results);

        // Si el permiso de la cámara no fue concedido, mostrar un mensaje y cerrar la app.
        if (!CameraPermissionHelper.hasCameraPermission(this)) {{
            Toast.makeText(this, "El permiso de cámara es necesario para usar la Realidad Aumentada.", Toast.LENGTH_LONG).show();
            finish();
        }}
    }}
}}
"""
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(codigo)
    return ruta

def crear_camera_permission_helper(logbox, package_name):
    """
    Crea el archivo CameraPermissionHelper.java en el paquete correcto.
    """
    helper_code = f"""package {package_name};

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.provider.Settings;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

/**
 * Helper para solicitar el permiso de cámara en tiempo de ejecución.
 */
public final class CameraPermissionHelper {{
  private static final int CAMERA_PERMISSION_CODE = 0;
  private static final String CAMERA_PERMISSION = Manifest.permission.CAMERA;

  /**
   * Verifica si la app tiene el permiso de cámara.
   */
  public static boolean hasCameraPermission(Activity activity) {{
    return ContextCompat.checkSelfPermission(activity, CAMERA_PERMISSION)
        == PackageManager.PERMISSION_GRANTED;
  }}

  /**
   * Solicita el permiso de cámara si aún no se ha concedido.
   */
  public static void requestCameraPermission(Activity activity) {{
    ActivityCompat.requestPermissions(
        activity, new String[]{{CAMERA_PERMISSION}}, CAMERA_PERMISSION_CODE);
  }}

  /**
   * Verifica si se debe mostrar una justificación para solicitar el permiso.
   * (No se usa en el flujo actual, pero es buena práctica tenerlo).
   */
  public static boolean shouldShowRequestPermissionRationale(Activity activity) {{
    return ActivityCompat.shouldShowRequestPermissionRationale(activity, CAMERA_PERMISSION);
  }}

  /**
   * Lanza la configuración de la aplicación para que el usuario pueda conceder el permiso manualmente.
   */
  public static void launchPermissionSettings(Activity activity) {{
    Intent intent = new Intent();
    intent.setAction(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
    intent.setData(Uri.fromParts("package", activity.getPackageName(), null));
    activity.startActivity(intent);
  }}
}}
"""
    try:
        java_dir = os.path.join(ANDROID_DIR, "app", "src", "main", "java", *package_name.split('.'))
        helper_path = os.path.join(java_dir, "CameraPermissionHelper.java")
        with open(helper_path, "w", encoding="utf-8") as f:
            f.write(helper_code)
        safe_log(logbox, f"✓ CameraPermissionHelper.java creado en: {helper_path}")
    except Exception as e:
        safe_log(logbox, f"✗ ERROR creando CameraPermissionHelper.java: {e}")
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

# La función safe_log ha sido movida a core/log.py

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

# La función verificar_entorno ha sido refactorizada y movida a core/env.py como validate_env

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
        safe_log(logbox, f"✓ AndroidManifest.xml corregido para: {package_name}")
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

def generar_marcador_nft(logbox, imagen_path, nombre_marcador):
    if not verificar_nft_marker_creator(logbox):
        return False
    
    try:
        # El script principal es app.js y se debe ejecutar con node
        script_path = os.path.join(NFT_CREATOR_PATH, "app.js")
        imagen_absoluta = os.path.abspath(imagen_path)
        
        # Comando corregido para usar 'node app.js -i <path>'
        cmd = ["node", "app.js", "-i", imagen_absoluta]
        
        safe_log(logbox, f"Ejecutando desde '{NFT_CREATOR_PATH}': {' '.join(cmd)}")
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
    Configura Gradle para usar el disco F cuando el disco C tiene poco espacio libre.
    Esta función modifica las configuraciones de Gradle para optimizar el uso de espacio en disco.
    
    Args:
        logbox: Widget de log para mostrar mensajes de estado
        nombre_paquete_limpio: El nombre del paquete para usar en el namespace.
    
    Returns:
        bool: True si la configuración fue exitosa, False en caso contrario
    """
    try:
        safe_log(logbox, "Configurando Gradle para usar disco F...")
        
        # 1. Configurar GRADLE_USER_HOME para usar disco F
        gradle_user_home = os.path.join(BASE_DIR, "gradle_cache")
        os.makedirs(gradle_user_home, exist_ok=True)
        
        # Establecer variable de entorno para la sesión actual
        os.environ['GRADLE_USER_HOME'] = gradle_user_home
        safe_log(logbox, f"✓ GRADLE_USER_HOME configurado en: {gradle_user_home}")
        
        # 2. Crear archivo gradle.properties en el directorio de trabajo del proyecto
        gradle_properties_path = os.path.join(PROJECT_DIR, "gradle.properties")
        gradle_properties_content = f"""# Configuración optimizada para disco F
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configureondemand=true

# Configuración de memoria optimizada
org.gradle.jvmargs=-Xmx4096m -XX:MaxPermSize=512m -XX:+HeapDumpOnOutOfMemoryError

# Directorio de cache personalizado en disco F
org.gradle.cache.dir={gradle_user_home.replace(os.sep, '/')}/caches

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
                                f.write(f'    buildDir = file("{os.path.join(BASE_DIR, "android_builds", nombre_paquete_limpio).replace(os.sep, "/")}")\n')
                            inserted = True
                safe_log(logbox, "✓ build.gradle actualizado con namespace y buildDir.")
        
        # 5. Crear directorios necesarios en disco F
        directories_to_create = [
            os.path.join(BASE_DIR, "gradle_cache"),
            os.path.join(BASE_DIR, "gradle_cache", "caches"), 
            os.path.join(BASE_DIR, "gradle_cache", "wrapper"),
            os.path.join(BASE_DIR, "android_builds"),
            os.path.join(BASE_DIR, "android_temp")
        ]
        
        for dir_path in directories_to_create:
            os.makedirs(dir_path, exist_ok=True)
        
        safe_log(logbox, f"✓ Directorios de cache creados en {BASE_DIR}")
        
        # 6. Configurar variables de entorno adicionales para Java/Android
        os.environ['JAVA_OPTS'] = f"-Djava.io.tmpdir={os.path.join(BASE_DIR, 'android_temp').replace(os.sep, '/')}"
        os.environ['GRADLE_OPTS'] = f"-Djava.io.tmpdir={os.path.join(BASE_DIR, 'android_temp').replace(os.sep, '/')} -Xmx4096m"
        
        safe_log(logbox, "✓ Configuración de Gradle en disco F completada exitosamente")
        
        return True
        
    except Exception as e:
        safe_log(logbox, f"✗ ERROR configurando Gradle en disco F: {e}")
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
                    
                    # Buscar y copiar APK desde la ruta de salida estándar de Gradle
                    apk_origen = os.path.join(
                        ANDROID_DIR, "app", "build", "outputs", "apk", "debug", "app-debug.apk"
                    )
                    
                    if os.path.exists(apk_origen):
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
                        safe_log(logbox, f"✗ No se encontró el APK en la ruta estándar: {apk_origen}")
                        # Listar archivos en directorio de salida para debug
                        output_dir = os.path.join(ANDROID_DIR, "app", "build", "outputs")
                        if os.path.exists(output_dir):
                            safe_log(logbox, f"Contenido de {output_dir}:")
                            for item in os.listdir(output_dir):
                                safe_log(logbox, f"  - {item}")
                                if os.path.isdir(os.path.join(output_dir, item)):
                                    for subitem in os.listdir(os.path.join(output_dir, item)):
                                        safe_log(logbox, f"    - {subitem}")
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
        if not validate_env(lambda msg: safe_log(self.logbox, msg)):
            messagebox.showerror("Error de entorno", "Faltan herramientas necesarias. Revisa el log.")

    def subir_portada(self):
        file_path = filedialog.askopenfilename(title="Selecciona la portada", filetypes=[("Imagenes", "*.png;*.jpg;*.jpeg")])
        if file_path:
            self.portada_path.set(file_path)
            self._portada_path_full = file_path

    def generar_iconos_desde_portada(self):
        if not self._portada_path_full:
            messagebox.showerror("Error", "No se ha seleccionado una portada.")
            return

        tamaños = {
            "mipmap-mdpi": 48,
            "mipmap-hdpi": 72,
            "mipmap-xhdpi": 96,
            "mipmap-xxhdpi": 144,
            "mipmap-xxxhdpi": 192
        }

        for carpeta, tamaño in tamaños.items():
            ruta_dir = os.path.join(ICONO_BASE_DIR, carpeta)
            os.makedirs(ruta_dir, exist_ok=True)
            ruta = os.path.join(ruta_dir, "ic_launcher.png")
            try:
                img = Image.open(self._portada_path_full).convert("RGBA")
                # Image.ANTIALIAS is deprecated in Pillow 10.0.0, but should work for now.
                # It was replaced by Image.Resampling.LANCZOS
                img = ImageOps.fit(img, (tamaño, tamaño), Image.ANTIALIAS)
                img.save(ruta)
                safe_log(self.logbox, f"✓ Icono generado: {ruta}")
            except Exception as e:
                safe_log(self.logbox, f"✗ Error generando icono {carpeta}: {e}")

    def exportar_log(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Archivo de texto", "*.txt")])
        if ruta:
            contenido = self.logbox.get("1.0", END)
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
            safe_log(self.logbox, f"✓ Log exportado a: {ruta}")

    def validar_paquete_completo(self):
        nombre = limpiar_nombre(self.nombre_libro.get())
        if not nombre:
            messagebox.showerror("Error", "Nombre del paquete requerido.")
            return False

        # Corregido: La ruta de marcadores debe apuntar al directorio, no al script app.js
        # También se buscan marcadores .fset (NFT) además de .patt
        rutas = {
            "Portada": os.path.join(PAQUETES_DIR, nombre, "portada.jpg"),
            "Modelos": os.path.join(MODELS_SHARED_DIR),
            "Marcadores": os.path.join(WWW_DIR, "assets", "markers"),
            "HTML": [os.path.join(PAQUETES_DIR, nombre, f) for f in ["index.html", "main-menu.html", "ar-viewer.html"]],
            "Claves": os.path.join(OUTPUT_APK_DIR, f"{nombre}_claves.txt")
        }

        estado = {
            "Portada": os.path.exists(rutas["Portada"]),
            "Modelos": any(f.startswith(nombre) and f.endswith(".glb") for f in os.listdir(rutas["Modelos"])) if os.path.exists(rutas["Modelos"]) else False,
            "Marcadores": any(f.startswith(nombre) and (f.endswith(".patt") or f.endswith(".fset")) for f in os.listdir(rutas["Marcadores"])) if os.path.exists(rutas["Marcadores"]) else False,
            "HTML": all(os.path.exists(f) for f in rutas["HTML"]),
            "Claves": os.path.exists(rutas["Claves"])
        }

        if not all(estado.values()):
            mensaje = f"❌ El paquete '{nombre}' está incompleto:\n"
            for k, v in estado.items():
                mensaje += f"{k}: {'✓' if v else '✗'}\n"
            
            safe_log(self.logbox, mensaje)
            messagebox.showwarning("Validación antes de APK", mensaje)
            return False

        safe_log(self.logbox, f"✓ Paquete '{nombre}' validado correctamente.")
        return True

    def generar_apk(self):
        if not self.validar_paquete_completo():
            return
        
        safe_log(self.logbox, f"--- Iniciando compilación de APK ---")
        try:
            # Lógica de compilación delegada a apk_build
            success = build_debug_apk(CAPACITOR_PROJECT, log=lambda msg: safe_log(self.logbox, msg))
            if success:
                messagebox.showinfo("Éxito", "APK compilado exitosamente. Revisa la carpeta de salida.")
                safe_log(self.logbox, f"--- Compilación de APK finalizada con éxito ---")
            else:
                messagebox.showerror("Error de Compilación", "Falló la compilación del APK. Revisa el log para más detalles.")
                safe_log(self.logbox, f"--- Compilación de APK fallida ---")
        except Exception as e:
            safe_log(self.logbox, f"✗ ERROR FATAL compilando APK: {e}")
            messagebox.showerror("Error", f"Ocurrió un error inesperado durante la compilación: {e}")

    def generar_paquete(self):
        nombre_app = self.nombre_libro.get()
        if not nombre_app:
            messagebox.showerror("Error", "Nombre del paquete requerido.")
            return

        safe_log(self.logbox, f"--- Iniciando generación de paquete para '{nombre_app}' ---")
        try:
            # Lógica delegada a los módulos de core
            app_id = f"com.librosdar.{limpiar_nombre(nombre_app)}"
            ensure_capacitor_app(CAPACITOR_TEMPLATE, CAPACITOR_PROJECT, app_id, nombre_app, log=lambda msg: safe_log(self.logbox, msg))

            # Por ahora, pasamos una lista de modelos vacía. Esto se puede conectar a la GUI más adelante.
            models_info = [] 
            propaganda = self.propaganda_var.get().strip()
            explicacion = self.explicacion_var.get().strip()
            write_frontend(
                WWW_DIR, 
                models_info, 
                log=lambda msg: safe_log(self.logbox, msg), 
                propaganda_url=propaganda, 
                explicacion_url=explicacion
            )
            safe_log(self.logbox, f"✓ Frontend web AR generado con enlaces dinámicos en: {WWW_DIR}")

            messagebox.showinfo("Éxito", f"Paquete '{nombre_app}' generado y listo para compilación.")
            safe_log(self.logbox, f"--- Paquete '{nombre_app}' generado exitosamente ---")
        except Exception as e:
            safe_log(self.logbox, f"✗ ERROR FATAL generando paquete: {e}")
            messagebox.showerror("Error", f"No se pudo generar el paquete: {e}")

    def lanzar_single_image(self):
        img_in = filedialog.askopenfilename(title="Selecciona la imagen de entrada")
        if not img_in: return
        model_out = filedialog.asksaveasfilename(defaultextension=".glb", title="Guardar modelo 3D GLB", filetypes=[("GLB file", "*.glb")])
        if img_in and model_out:
            threading.Thread(target=lambda: generate_single_image_model(img_in, model_out, log=lambda msg: safe_log(self.logbox, msg)), daemon=True).start()
            safe_log(self.logbox, "Iniciando pipeline Single-Image en segundo plano...")

    def lanzar_multiview(self):
        img_dir = filedialog.askdirectory(title="Selecciona la carpeta con las fotos")
        if not img_dir: return
        model_out = filedialog.asksaveasfilename(defaultextension=".glb", title="Guardar modelo 3D GLB", filetypes=[("GLB file", "*.glb")])
        if img_dir and model_out:
            threading.Thread(target=lambda: generate_multiview_model(img_dir, model_out, log=lambda msg: safe_log(self.logbox, msg)), daemon=True).start()
            safe_log(self.logbox, "Iniciando pipeline Multi-View en segundo plano...")

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
        Button(acciones_frame, text="Generar Íconos", command=self.generar_iconos_desde_portada, width=18).pack(pady=5)
        Button(acciones_frame, text="Iniciar Servidor y Ngrok", bg="#ffc107", fg="black",
               command=self.iniciar_servidor_ngrok, width=18, height=2).pack(pady=5)
        Button(acciones_frame, text="Ver Modelo 3D", command=self.ver_modelo_actual, width=18).pack(pady=5)

        Label(acciones_frame, text="9. Verificación:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(20, 10))
        Button(acciones_frame, text="Verificar Conexión", command=self.verify_backend_connection, width=18).pack(pady=5)
        Button(acciones_frame, text="Ver Claves en BD", command=self.view_activation_keys, width=18).pack(pady=5)

        Button(acciones_frame, text="Limpiar Formulario", fg="black",
               command=self.limpiar_todo, width=18).pack(pady=20)

        # Nuevo frame para los pipelines 3D
        gen3d_frame = Frame(main, pady=20)
        gen3d_frame.pack(side=LEFT, fill=Y, padx=(20, 0))
        Label(gen3d_frame, text="10. Generación 3D:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))
        Button(gen3d_frame, text="Desde 1 Imagen", bg="#17a2b8", fg="white",
               command=self.lanzar_single_image, width=18, height=2).pack(pady=5)
        Button(gen3d_frame, text="Desde Múltiples Vistas", bg="#17a2b8", fg="white",
               command=self.lanzar_multiview, width=18, height=2).pack(pady=5)

        log_frame = Frame(self.root, padx=10, pady=10)
        log_frame.pack(side=RIGHT, fill=BOTH, expand=True)
        Label(log_frame, text="Log de la Aplicación:", font=("Segoe UI", 10, "bold")).pack(anchor='w')
        self.logbox = Text(log_frame, height=38, width=70, bg="#f4f4f4", state=DISABLED, font=("Consolas", 9))
        self.logbox.pack(side=LEFT, fill=BOTH, expand=True)
        Scrollbar(log_frame, command=self.logbox.yview, orient=VERTICAL).pack(side=RIGHT, fill=Y)
        self.logbox.config(yscrollcommand=lambda f, l: ()) # Deshabilita el scroll automático para evitar saltos

        Button(log_frame, text="Copiar Log", command=self.copy_log_to_clipboard).pack(pady=5)
        Button(log_frame, text="Exportar Log", command=self.exportar_log).pack(pady=5)

        self.label_progreso = Label(self.root, text="Listo.", relief="sunken", anchor="w", padx=5)
        self.label_progreso.pack(side="bottom", fill="x")

        # =========================
        # Módulos avanzados integrados
        # =========================

        def generar_paquete_completo():
            contexto = "F:/linux/3d-AR/contexto/programa_activo.txt"
            if not os.path.exists(contexto):
                mostrar_log("Error", "❌ No hay programa activo.")
                return
            with open(contexto, "r", encoding="utf-8") as f:
                nombre = f.read().strip()
            base = "F:/linux/3d-AR/"
            rutas = {
                "Modelos": os.path.join(base, "models"),
                "Instrucciones": os.path.join(base, "hunyuan3d")
            }
            estado = {
                "Modelos": any(f.startswith(nombre) and f.endswith(".glb") for f in os.listdir(rutas["Modelos"])),
                "Instrucciones": any(f.startswith(nombre) and f.endswith(".json") for f in os.listdir(rutas["Instrucciones"]))
            }
            if not all(estado.values()):
                mensaje = f"❌ El programa '{nombre}' no tiene todos los componentes necesarios:\n"
                for k, v in estado.items():
                    mensaje += f"{k}: {'✅' if v else '❌ Faltante'}\n"
                mostrar_log("Validación incompleta", mensaje)
                return
            generar_modelos()
            generar_marcadores()
            generar_apk()
            resumen = f"✅ Paquete completo generado para: {nombre}\n\n"
            resumen += "🧠 Modelos IA generados\n"
            resumen += "🎯 Marcadores NFT generados\n"
            resumen += "📲 APK empaquetado\n"
            mostrar_log("Paquete completo", resumen)

        def ver_estado_programa_gui():
            contexto = "F:/linux/3d-AR/contexto/programa_activo.txt"
            if not os.path.exists(contexto):
                mostrar_log("Error", "❌ No hay programa activo.")
                return
            with open(contexto, "r", encoding="utf-8") as f:
                nombre = f.read().strip()
            base = "F:/linux/3d-AR/"
            rutas = {
                "Portada": os.path.join(base, "paquetes", nombre, "portada.jpg"),
                "Modelos": os.path.join(base, "models"),
                "Marcadores": os.path.join(base, "nft-creator"),
                "HTML": [os.path.join(base, "paquetes", nombre, f) for f in ["index.html", "main-menu.html", "ar-viewer.html"]],
                "Claves": os.path.join(base, "output-apk", f"{nombre}_claves.txt"),
                "APK": os.path.join(base, "output-apk", nombre, f"{nombre}.apk")
            }
            estado = {
                "Portada": os.path.exists(rutas["Portada"]),
                "Modelos": any(f.startswith(nombre) and f.endswith(".glb") for f in os.listdir(rutas["Modelos"])),
                "Marcadores": any(f.startswith(nombre) and f.endswith(".patt") for f in os.listdir(rutas["Marcadores"])),
                "HTML": all(os.path.exists(f) for f in rutas["HTML"]),
                "Claves": os.path.exists(rutas["Claves"]),
                "APK": os.path.exists(rutas["APK"])
            }
            mensaje = f"Estado del paquete '{nombre}':\n"
            for k, v in estado.items():
                mensaje += f"  {k}: {'✓' if v else '✗'}\n"
            mostrar_log("Estado del paquete", mensaje)

        def visor_3d_con_ia():
            import webview
            contexto = "F:/linux/3d-AR/contexto/programa_activo.txt"
            if not os.path.exists(contexto):
                mostrar_log("Error", "❌ No hay programa activo.")
                return
            with open(contexto, "r", encoding="utf-8") as f:
                nombre = f.read().strip()
            modelo_url = f"file:///F:/linux/3d-AR/www/viewer.html?modelo={nombre}.glb"
            webview.create_window(f"Visor 3D + IA - {nombre}", modelo_url, width=900, height=700)
            webview.start()

        def borrar_paquetes_generados():
            import shutil
            base = "F:/AR_APK/"
            carpetas = [os.path.join(base, d) for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
            for c in carpetas:
                try:
                    shutil.rmtree(c)
                except Exception as e:
                    print(f"Error al borrar {c}: {e}")
            mostrar_log("Borrado de paquetes", "✅ Todas las carpetas de paquetes han sido eliminadas.")

        def ver_apk_generado():
            import subprocess
            contexto = "F:/linux/3d-AR/contexto/programa_activo.txt"
            if not os.path.exists(contexto):
                mostrar_log("Error", "❌ No hay programa activo.")
                return
            with open(contexto, "r", encoding="utf-8") as f:
                nombre = f.read().strip()
            ruta = f"F:/AR_APK/{nombre}/APK_FINAL/"
            if os.path.exists(ruta):
                subprocess.Popen(["explorer", ruta])
                mostrar_log("Abrir carpeta APK", f"Abriendo carpeta: {ruta}")
            else:
                mostrar_log("Abrir carpeta APK", "No se encontró la carpeta del APK generado.")

        def ver_logs():
            base = "F:/linux/3d-AR/diagnostics/"
            logs = [f for f in os.listdir(base) if f.endswith('.log')]
            ventana = tk.Toplevel()
            ventana.title("Navegador de logs")
            ventana.geometry("700x500")
            combo = ttk.Combobox(ventana, values=logs, state="readonly", width=60)
            combo.pack(pady=10)
            texto = tk.Text(ventana, wrap="word")
            texto.pack(expand=True, fill="both")
            def cargar_log():
                log = combo.get()
                if log:
                    with open(os.path.join(base, log), "r", encoding="utf-8") as f:
                        contenido = f.read()
                    texto.delete("1.0", tk.END)
                    texto.insert(tk.END, contenido)
            tk.Button(ventana, text="Cargar log", command=cargar_log).pack(pady=5)

        # Botones y acciones en la GUI
        scroll_frame = Frame(self.root)
        scroll_frame.pack(side=LEFT, fill=BOTH, expand=True)

        def boton(titulo, accion):
            tk.Button(scroll_frame, text=titulo, command=accion, width=50).pack(pady=4)

        # Secciones
        tk.Label(scroll_frame, text="🧩 1. Revisión de estructura", font=("Arial", 12, "bold")).pack(pady=6)
        boton("🔍 Revisar estructura y programas", mostrar_resultado_revision)

        tk.Label(scroll_frame, text="🧩 2. Selección de programa activo", font=("Arial", 12, "bold")).pack(pady=6)
        boton("📦 Seleccionar programa activo", selector_programa_activo)

        tk.Label(scroll_frame, text="🧩 3. Generación de APK", font=("Arial", 12, "bold")).pack(pady=6)
        boton("📲 Generar APK", generar_apk)
        boton("📦 Generar paquete completo", generar_paquete_completo)
        boton("🧹 Borrar paquetes generados", borrar_paquetes_generados)
        boton("📂 Ver APK generado", ver_apk_generado)

        tk.Label(scroll_frame, text="🧩 4. Generación de modelos", font=("Arial", 12, "bold")).pack(pady=6)
        boton("🧠 Generar modelos IA", generar_modelos)

        tk.Label(scroll_frame, text="🧩 5. Estado del paquete", font=("Arial", 12, "bold")).pack(pady=6)
        boton("🔎 Ver estado del paquete", ver_estado_programa_gui)

        tk.Label(scroll_frame, text="🧩 6. Visor 3D e IA", font=("Arial", 12, "bold")).pack(pady=6)
        boton("👁️ Visor 3D + instrucciones IA", visor_3d_con_ia)

        tk.Label(scroll_frame, text="🧩 7. Activación de claves", font=("Arial", 12, "bold")).pack(pady=6)
        boton("🔑 Activar claves APK", activar_claves_apk)

        tk.Label(scroll_frame, text="🧩 8. Navegador de logs", font=("Arial", 12, "bold")).pack(pady=6)
        boton("📜 Ver logs", ver_logs)

        ventana.mainloop()

import tkinter as tk
from tkinter import ttk
import os
import subprocess
import shutil
try:
    import webview
except ImportError:
    webview = None

# La función mostrar_log ha sido movida a core/log.py

# Stubs para funciones de pipeline
def generar_modelos():
    print("Stub: generar_modelos ejecutado")

def generar_marcadores():
    print("Stub: generar_marcadores ejecutado")

def activar_claves_apk():
    print("Stub: activar_claves_apk ejecutado")

def selector_programa_activo():
    print("Stub: selector_programa_activo ejecutado")

def mostrar_resultado_revision():
    print("Stub: mostrar_resultado_revision ejecutado")

def generar_codigo_bpy(instruccion):
    # Se usa una ruta relativa para portabilidad, en lugar de depender de BASE_DIR
    contexto_path = os.path.join("contexto", "context_phi2.json")
    if os.path.exists(contexto_path):
        with open(contexto_path, "r", encoding="utf-8") as f:
            contexto = json.load(f)
        if instruccion in contexto:
            return contexto[instruccion]
    return f"# Código bpy para: {instruccion}\n# TODO: implementar lógica"

# === PANEL DE GENERACIÓN 3D IA EN LA GUI PRINCIPAL ===
def panel_ia_generacion(root):
    frame_ia = LabelFrame(root, text="Generación 3D IA", padx=10, pady=10)
    frame_ia.pack(fill="x", padx=10, pady=5)
    Label(frame_ia, text="Ruta de entrada (imagen/carpeta):").grid(row=0, column=0, sticky="w")
    entry_input = Entry(frame_ia, width=60)
    entry_input.grid(row=0, column=1, padx=5)
    Label(frame_ia, text="Nombre de salida:").grid(row=1, column=0, sticky="w")
    entry_output = Entry(frame_ia, width=40)
    entry_output.grid(row=1, column=1, padx=5)
    Label(frame_ia, text="Instrucción IA (ej: 'rotar el modelo 90 grados'):").grid(row=3, column=0, sticky="w")
    entry_instruccion = Entry(frame_ia, width=60)
    entry_instruccion.grid(row=3, column=1, padx=5)

    def lanzar_triposr():
        input_path = entry_input.get()
        output_name = entry_output.get()
        if not input_path or not output_name:
            messagebox.showerror("Error", "Debes especificar la ruta de entrada y el nombre de salida.")
            return
        ejecutar_triposr(input_path, output_name)
    def lanzar_hunyuan3d():
        input_path = entry_input.get()
        output_name = entry_output.get()
        if not input_path or not output_name:
            messagebox.showerror("Error", "Debes especificar la ruta de entrada y el nombre de salida.")
            return
        ejecutar_hunyuan3d(input_path, output_name)
    def lanzar_phi2():
        input_path = entry_input.get()
        output_name = entry_output.get()
        if not input_path or not output_name:
            messagebox.showerror("Error", "Debes especificar la ruta de entrada y el nombre de salida.")
            return
        ejecutar_phi2(input_path, output_name)
    Button(frame_ia, text="Generar con TripoSR", command=lanzar_triposr).grid(row=2, column=0, pady=8)
    Button(frame_ia, text="Generar con Hunyuan3D", command=lanzar_hunyuan3d).grid(row=2, column=1, pady=8)
    Button(frame_ia, text="Generar con Phi-2", command=lanzar_phi2).grid(row=2, column=2, pady=8)

    def on_instruccion():
        instruccion = entry_instruccion.get().strip()
        input_path = entry_input.get()
        output_name = entry_output.get()
        if not instruccion:
            messagebox.showerror("Error", "Debes escribir una instrucción en lenguaje natural.")
            return
        if not input_path or not output_name:
            messagebox.showerror("Error", "Debes especificar la ruta de entrada y el nombre de salida.")
            return
        
        codigo_bpy = generar_codigo_bpy(instruccion)
        # Guardar el código bpy en un script temporal
        script_path = os.path.join(OUTPUT_3DMODELS_DIR, f"temp_bpy_{output_name}.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(codigo_bpy)
        # Ejecutar Blender en background con el script
        export_path = os.path.join(OUTPUT_3DMODELS_DIR, output_name)
        modelo_base = input_path
        blender_cmd = [BLENDER_EXE, modelo_base, "--background", "--python", script_path, "--", export_path]
        try:
            subprocess.run(blender_cmd, check=True)
            messagebox.showinfo("Phi-2", f"Modelo actualizado y exportado en: {export_path}")
        except Exception as e:
            messagebox.showerror("Error Blender", str(e))
        # Recargar visor 3D si está disponible
        try:
            from visor3d_webview import lanzar_visor_3d
            lanzar_visor_3d(export_path)
        except Exception:
            pass
    Button(frame_ia, text="Ejecutar instrucción IA (Phi-2)", command=on_instruccion).grid(row=4, column=0, columnspan=2, pady=8)

    return frame_ia

###################################################
# === FUNCIONES PARA EJECUTAR MODELOS IA ===
###################################################
def ejecutar_triposr(input_path, output_name):
    """
    Ejecuta TripoSR para generar un modelo 3D a partir de un input (imagen o carpeta).
    Guarda el resultado en OUTPUT_3DMODELS_DIR/output_name
    """
    if not os.path.exists(TRIPOSR_SCRIPT):
        messagebox.showerror("Error", "No se encontró el script principal de TripoSR.")
        return
    if not os.path.exists(TRIPOSR_WEIGHTS):
        messagebox.showerror("Error", "No se encontró el modelo de pesos de TripoSR.")
        return
    output_path = os.path.join(OUTPUT_3DMODELS_DIR, output_name)
    cmd = f'python "{TRIPOSR_SCRIPT}" --input "{input_path}" --output "{output_path}" --config "{TRIPOSR_CONFIG}" --weights "{TRIPOSR_WEIGHTS}"'
    try:
        subprocess.run(cmd, shell=True, check=True)
        messagebox.showinfo("TripoSR", f"Modelo generado en: {output_path}")
    except Exception as e:
        messagebox.showerror("Error TripoSR", str(e))

def ejecutar_hunyuan3d(input_path, output_name):
    """
    Ejecuta Hunyuan3D para generar un modelo 3D a partir de un input (imagen o carpeta).
    Guarda el resultado en OUTPUT_3DMODELS_DIR/output_name
    """
    if not os.path.exists(HUNYUAN3D_SCRIPT):
        messagebox.showerror("Error", "No se encontró el script principal de Hunyuan3D.")
        return
    if not os.path.exists(HUNYUAN3D_WEIGHTS):
        messagebox.showerror("Error", "No se encontró el modelo de pesos de Hunyuan3D.")
        return
    output_path = os.path.join(OUTPUT_3DMODELS_DIR, output_name)
    cmd = f'python "{HUNYUAN3D_SCRIPT}" --input "{input_path}" --output "{output_path}" --config "{HUNYUAN3D_CONFIG}" --weights "{HUNYUAN3D_WEIGHTS}"'
    try:
        subprocess.run(cmd, shell=True, check=True)
        messagebox.showinfo("Hunyuan3D", f"Modelo generado en: {output_path}")
    except Exception as e:
        messagebox.showerror("Error Hunyuan3D", str(e))

def ejecutar_phi2(input_path, output_name):
    """
    Ejecuta Phi-2 para generar un modelo 3D a partir de un input (imagen o carpeta).
    Guarda el resultado en OUTPUT_3DMODELS_DIR/output_name
    """
    if not os.path.exists(PHI2_SCRIPT):
        messagebox.showerror("Error", "No se encontró el script principal de Phi-2.")
        return
    if not os.path.exists(PHI2_WEIGHTS):
        messagebox.showerror("Error", "No se encontró el modelo de pesos de Phi-2.")
        return
    output_path = os.path.join(OUTPUT_3DMODELS_DIR, output_name)
    cmd = f'python "{PHI2_SCRIPT}" --input "{input_path}" --output "{output_path}" --config "{PHI2_CONFIG}" --weights "{PHI2_WEIGHTS}"'
    try:
        subprocess.run(cmd, shell=True, check=True)
        messagebox.showinfo("Phi-2", f"Modelo generado en: {output_path}")
    except Exception as e:
        messagebox.showerror("Error Phi-2", str(e))

if __name__ == "__main__":
    root = Tk()
    app = GeneradorGUI(root)
    root.mainloop()


















