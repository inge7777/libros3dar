<?php
require_once 'api/config.php';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generador AR LibrosDAR - Versión Definitiva</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding-bottom: 200px; }
        .main-container { background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); margin: 35px auto; max-width: 1400px; overflow: hidden; }
        .header { background: linear-gradient(135deg, #2c3e50, #3498db); color: white; padding: 20px; text-align: center; border-radius: 15px 15px 0 0; }
        .tab-container { display: flex; background: #f8f9fa; }
        .tab { padding: 15px 25px; cursor: pointer; background: #f8f9fa; border: none; flex: 1; font-weight: 600; transition: all 0.3s ease; border-radius: 0; border-bottom: 3px solid transparent; }
        .tab.active { border-bottom-color: #3498db; background-color: #e3f2fd; }
        .tab-content { display: none; padding: 30px; min-height: 400px; }
        .tab-content.active { display: block; }
        .file-upload-area { border: 3px dashed #ddd; border-radius: 10px; padding: 40px; text-align: center; cursor: pointer; background: #f8f9fa; margin-bottom: 10px; transition: all 0.3s ease;}
        .file-upload-area.dragover { border-color: #3498db; background: #e9ecef; }
        .file-item { display: flex; justify-content: space-between; align-items: center; padding: 15px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; background: white; }
        #three-model-viewer, #ar-viewer-container { width:100%; height:400px; background:#eee; border-radius: 10px; position: relative; }
        
        /* AR Fullscreen Fix */
        #ar-viewer-container.fullscreen { position: fixed !important; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 9998 !important; }
        #ar-viewer-container.fullscreen a-scene { position: absolute !important; top: 0; left: 0; width: 100%; height: 100%; z-index: 9999 !important; }
        .ar-close-btn { position: fixed; top: 20px; right: 20px; z-index: 10000 !important; background: rgba(0,0,0,0.5); color: white; border: none; border-radius: 50%; width: 50px; height: 50px; font-size: 20px; cursor: pointer; display: none; }
        
        /* Log Panel Styles */
        .log-panel { position: fixed; bottom: 0; left: 0; right: 0; height: 200px; background: #1a1a1a; color: #00ff00; font-family: 'Courier New', monospace; font-size: 14px; padding: 15px; overflow-y: auto; border-top: 2px solid #3498db; z-index: 10001; display: none; }
        .log-panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 5px; border-bottom: 1px solid #444; }
        .log-timestamp { color: #888; }
        .log-toggle-btn { position: fixed; bottom: 10px; right: 10px; z-index: 10002; background: #2c3e50; color: white; border: none; border-radius: 50%; width: 50px; height: 50px; font-size: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.3); }
        .log-toggle-btn.active { background-color: #e74c3c; }
    </style>
    
    <!-- Librerías JS en el orden correcto y sin conflictos -->
    <!-- A-Frame carga su propia versión de Three.js (r125). No debemos cargarla por separado. -->
    <script src="https://aframe.io/releases/1.2.0/aframe.min.js"></script>
    <!-- Cargamos los complementos de Three.js de la misma versión que A-Frame (r125) -->
    <script src="https://cdn.jsdelivr.net/npm/three@0.125.2/examples/js/controls/OrbitControls.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.125.2/examples/js/loaders/GLTFLoader.js"></script>
    <!-- AR.js para A-Frame -->
    <script src="https://cdn.jsdelivr.net/gh/AR-js-org/AR.js/aframe/build/aframe-ar.js"></script>

</head>
<body>
    <div id="main-app-container">
        <div class="container-fluid">
            <div class="main-container">
                <div class="header">
                    <h1><i class="fas fa-cube"></i> Generador AR LibrosDAR</h1>
                <p>Versión Definitiva y Funcional</p>
            </div>
            
            <div class="tab-container">
                <button class="tab active" data-tab="1"><i class="fas fa-upload"></i> Cargar Contenido</button>
                <button class="tab" data-tab="2"><i class="fas fa-eye"></i> Visualizar Modelos</button>
                <button class="tab" data-tab="3"><i class="fas fa-camera"></i> Realidad Aumentada</button>
                <button class="tab" data-tab="4"><i class="fas fa-cogs"></i> Generar Aplicación</button>
            </div>

            <!-- Tab 1: Carga de Archivos -->
            <div class="tab-content active" id="tab-1">
                <h3><i class="fas fa-cloud-upload-alt"></i> 1. Cargar Imágenes y Modelos 3D</h3>
                <div class="row">
                    <div class="col-md-6">
                        <h5>Imágenes Marcadoras (.jpg, .png)</h5>
                        <div class="file-upload-area" id="image-upload-area"><i class="fas fa-images fa-3x mb-3"></i><p>Haz clic o arrastra imágenes aquí</p></div>
                        <input type="file" id="image-input" multiple accept="image/*" style="display: none;">
                        <div id="image-list"></div>
                        <button class="btn btn-success w-100 mt-3" id="generate-patt-btn"><i class="fas fa-magic"></i> Generar Archivos de Patrones</button>
                    </div>
                    <div class="col-md-6">
                        <h5>Modelos 3D (.glb, .gltf)</h5>
                        <div class="file-upload-area" id="model-upload-area"><i class="fas fa-cube fa-3x mb-3"></i><p>Haz clic o arrastra modelos 3D aquí</p></div>
                        <input type="file" id="model-input" multiple accept=".glb,.gltf" style="display: none;">
                        <div id="model-list"></div>
                    </div>
                </div>
            </div>

            <!-- Tab 2: Visualizador 3D -->
            <div class="tab-content" id="tab-2">
                <h3><i class="fas fa-eye"></i> 2. Visualización de Modelos 3D</h3>
                <div class="mb-3">
                    <label for="model-selector-3d" class="form-label">Selecciona un modelo para visualizar:</label>
                    <select id="model-selector-3d" class="form-select"></select>
                </div>
                <div id="three-model-viewer"><p class="text-muted">El visor 3D aparecerá aquí.</p></div>
            </div>

            <!-- Tab 3: Realidad Aumentada -->
            <div class="tab-content" id="tab-3">
                <h3><i class="fas fa-camera"></i> 3. Prueba de Realidad Aumentada</h3>
                <p>Presiona el botón para abrir la vista de Realidad Aumentada en una nueva ventana. La aplicación detectará automáticamente cualquier marcador que le muestres a la cámara.</p>
                <div class="text-center mt-4">
                    <button class="btn btn-primary btn-lg" id="view-ar-btn"><i class="fas fa-external-link-alt"></i> Abrir Visor de Realidad Aumentada</button>
                </div>
            </div>

            <!-- Tab 4: Generación de APK -->
            <div class="tab-content" id="tab-4">
                <h3><i class="fas fa-cogs"></i> 4. Generar Aplicación Final</h3>
                <div class="alert alert-warning" role="alert">
                    <h4 class="alert-heading"><i class="fas fa-exclamation-triangle"></i> Nota Importante del Servidor</h4>
                    <p>Si la compilación del APK falla con el error <strong>"android platform has not been added yet"</strong>, significa que se necesita una configuración inicial en el servidor.</p>
                    <hr>
                    <p class="mb-0">El administrador del servidor debe ejecutar el comando <code>npx cap add android</code> en el directorio de la plantilla de Capacitor una única vez para solucionarlo.</p>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3"><label for="app-name" class="form-label">Nombre de la Aplicación</label><input type="text" class="form-control" id="app-name" placeholder="Mi App de AR"></div>
                        <div class="mb-3"><label for="package-name" class="form-label">Nombre del Paquete (ej: com.miempresa.miapp)</label><input type="text" class="form-control" id="package-name" placeholder="com.ejemplo.miaplicacion"></div>
                    </div>
                    <div class="col-md-6">
                        <button class="btn btn-primary w-100 mb-3" id="generate-package-btn"><i class="fas fa-box"></i> 2. Generar Paquete Web</button>
                        <button class="btn btn-secondary w-100" id="generate-apk-btn"><i class="fas fa-mobile-alt"></i> 3. Compilar APK</button>
                        <div id="apk-download-container" class="mt-3"></div>
                    </div>
                </div>
            </div>

        </div>
    </div>
    </div>
    
    <!-- Botón y Panel de Logs -->
    <button class="log-toggle-btn" id="log-toggle-btn"><i class="fas fa-terminal"></i></button>
    <div class="log-panel" id="log-panel">
        <div class="log-panel-header">
            <h5>Logs del Sistema</h5>
            <div>
                <button class="btn btn-sm btn-outline-light me-2" id="clear-log-btn"><i class="fas fa-trash"></i> Limpiar Log</button>
                <button class="btn btn-sm btn-danger" id="reset-all-btn"><i class="fas fa-power-off"></i> Reiniciar Todo</button>
            </div>
        </div>
        <div id="log-content"></div>
    </div>
    
    <!-- Botón para cerrar la vista AR -->
    <button class="ar-close-btn" id="ar-close-btn">✖</button>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script src="assets/js/app.js"></script>
</body>
</html>
