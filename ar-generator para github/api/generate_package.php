<?php
require_once 'config.php';

// --- Funciones de Ayuda ---

/**
 * Copia un directorio y todo su contenido de forma recursiva.
 * @param string $src Directorio de origen.
 * @param string $dst Directorio de destino.
 */
function recursive_copy($src, $dst) {
    if (!is_dir($dst)) {
        mkdir($dst, 0777, true);
    }
    $dir = opendir($src);
    while (($file = readdir($dir)) !== false) {
        if (($file != '.') && ($file != '..')) {
            if (is_dir($src . '/' . $file)) {
                recursive_copy($src . '/' . $file, $dst . '/' . $file);
            } else {
                copy($src . '/' . $file, $dst . '/' . $file);
            }
        }
    }
    closedir($dir);
}

/**
 * Ejecuta un comando y devuelve un array con el éxito, la salida y el código de retorno.
 * @param string $command El comando a ejecutar.
 * @return array
 */
function execute_command($command) {
    $output = [];
    $return_code = 0;
    exec($command . ' 2>&1', $output, $return_code); // Redirigir stderr a stdout
    return [
        'success' => $return_code === 0,
        'output' => implode("\n", $output),
        'return_code' => $return_code
    ];
}


// --- Lógica Principal ---

$response = ['success' => false, 'message' => 'Petición inválida.'];

$input = json_decode(file_get_contents('php://input'), true);

if (!$input || !isset($input['appName']) || !isset($input['packageName']) || !isset($input['files'])) {
    echo json_encode($response);
    exit;
}

$appName = preg_replace('/[^a-zA-Z0-9_-]/', '', $input['appName']);
$packageName = $input['packageName'];
$files = $input['files'];

// 1. Crear directorio único para el paquete
$packageDirName = $appName . '_' . time();
$packagePath = PACKAGES_PATH . '/' . $packageDirName;

if (!mkdir($packagePath, 0777, true)) {
    $response['message'] = "Error: No se pudo crear el directorio del paquete en '$packagePath'.";
    echo json_encode($response);
    exit;
}

try {
    // 2. Copiar la plantilla de Capacitor
    recursive_copy(CAPACITOR_TEMPLATE, $packagePath);

    // 3. Modificar capacitor.config.json
    $capacitorConfigPath = $packagePath . '/capacitor.config.json';
    if (file_exists($capacitorConfigPath)) {
        $configJson = json_decode(file_get_contents($capacitorConfigPath), true);
        $configJson['appName'] = $appName;
        $configJson['appId'] = $packageName;
        file_put_contents($capacitorConfigPath, json_encode($configJson, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
    } else {
        throw new Exception("No se encontró capacitor.config.json en la plantilla.");
    }
    
    // Rutas de assets dentro del nuevo paquete
    $wwwAssetsPath = $packagePath . '/www/assets';
    $modelsDestDir = $wwwAssetsPath . '/models';
    $imagesDestDir = $wwwAssetsPath . '/images';
    $patternsDestDir = $wwwAssetsPath . '/patterns';
    mkdir($modelsDestDir, 0777, true);
    mkdir($imagesDestDir, 0777, true);
    mkdir($patternsDestDir, 0777, true);


    // 4. Procesar y copiar archivos
    // Copiar imágenes
    foreach ($files['images'] as $image) {
        $sourcePath = UPLOADS_PATH . '/images/' . $image['name'];
        $destPath = $imagesDestDir . '/' . $image['name'];
        if (file_exists($sourcePath)) {
            copy($sourcePath, $destPath);
            
            // ** Simulación de generación de patrones .patt **
            // En una implementación real, aquí se llamaría a la herramienta de generación de patrones
            // Por ejemplo: execute_command("path/to/patt-generator.exe $destPath $patternsDestDir/" . pathinfo($image['name'], PATHINFO_FILENAME) . ".patt");
            $patternContent = "AR_PATTERN_FILE_FOR_" . $image['name'];
            file_put_contents($patternsDestDir . '/' . pathinfo($image['name'], PATHINFO_FILENAME) . ".patt", $patternContent);
        }
    }

    // Copiar y convertir modelos
    foreach ($files['models'] as $model) {
        $sourcePath = UPLOADS_PATH . '/models/' . $model['name'];
        $fileExtension = strtolower(pathinfo($model['name'], PATHINFO_EXTENSION));
        $outputName = pathinfo($model['name'], PATHINFO_FILENAME) . '.glb';
        $destPath = $modelsDestDir . '/' . $outputName;

        if (file_exists($sourcePath)) {
            if ($fileExtension === 'glb' || $fileExtension === 'gltf') {
                copy($sourcePath, $destPath);
            } else {
                // ** Conversión con Blender **
                // Se asume que existe un script `blender_convert.py` en la carpeta `api/`
                $blenderScript = __DIR__ . '/blender_convert.py';
                $command = '"' . BLENDER_PATH . '" --background --python "' . $blenderScript . '" -- --input "' . $sourcePath . '" --output "' . $destPath . '"';
                
                $result = execute_command($command);
                if (!$result['success']) {
                    throw new Exception("Error al convertir el modelo '{$model['name']}' con Blender. Salida: " . $result['output']);
                }
            }
        }
    }

    // 5. Crear archivo de mapeo (asset-map.json) para que la app sepa qué modelo corresponde a qué patrón
    $assetMap = [];
    // Esta lógica asume que el primer modelo va con el primer patrón, etc.
    // Una implementación más robusta requeriría una UI para mapearlos.
    $patternFiles = glob($patternsDestDir . '/*.patt');
    $modelFiles = glob($modelsDestDir . '/*.glb');

    for($i = 0; $i < count($patternFiles); $i++) {
        if(isset($modelFiles[$i])) {
            $patternName = basename($patternFiles[$i]);
            $modelName = basename($modelFiles[$i]);
            $assetMap[$patternName] = "assets/models/" . $modelName;
        }
    }
    file_put_contents($wwwAssetsPath . '/asset-map.json', json_encode($assetMap, JSON_PRETTY_PRINT));


    $response['success'] = true;
    $response['message'] = 'Paquete web generado con éxito en ' . $packageDirName;
    $response['packagePath'] = $packagePath;

} catch (Exception $e) {
    $response['message'] = 'Error durante la generación del paquete: ' . $e->getMessage();
    // Limpiar directorio del paquete en caso de error
    // (Implementación de borrado recursivo omitida por brevedad)
}

echo json_encode($response);
?>
