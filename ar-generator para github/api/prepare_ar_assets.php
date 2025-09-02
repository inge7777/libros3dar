<?php
header('Content-Type: application/json; charset=UTF-8');
error_reporting(E_ALL);
ini_set('display_errors', 1);

$response = ['success' => false, 'message' => 'Error desconocido durante la preparación de assets.'];

try {
    $projectRoot = dirname(__DIR__);
    define('UPLOADS_PATH', $projectRoot . '/uploads');

    $patternsSourceDir = UPLOADS_PATH . '/patterns';
    $modelsSourceDir = UPLOADS_PATH . '/models';
    
    $assetsDestDir = $projectRoot . '/assets';
    $patternsDestDir = $assetsDestDir . '/patterns';
    $modelsDestDir = $assetsDestDir . '/models';
    
    $dataDestDir = $projectRoot . '/data';
    $assetMapPath = $assetsDestDir . '/asset-map.json';
    
    // CORRECTED: The source and destination for camera_para.dat are now the same public 'data' directory.
    // The user is responsible for placing the file here. The script just verifies it.
    $cameraParaPath = $dataDestDir . '/camera_para.dat';

    // Helper Function
    function copy_directory_contents($source, $destination) {
        if (!is_dir($source)) return; // Don't fail if uploads sub-dir doesn't exist yet
        if (!is_dir($destination) && !mkdir($destination, 0777, true)) {
            throw new Exception("No se pudo crear directorio destino: $destination");
        }
        $items = array_diff(scandir($source), ['..', '.']);
        foreach ($items as $item) {
            $sourcePath = $source . '/' . $item;
            $destPath = $destination . '/' . $item;
            if (is_file($sourcePath)) {
                if (!copy($sourcePath, $destPath)) {
                    throw new Exception("No se pudo copiar el archivo: $sourcePath a $destPath");
                }
            }
        }
    }

    // 1. Create destination directories if they don't exist
    foreach ([$assetsDestDir, $patternsDestDir, $modelsDestDir, $dataDestDir] as $dir) {
        if (!is_dir($dir) && !mkdir($dir, 0777, true)) {
            throw new Exception("No se pudo crear el directorio: $dir");
        }
    }

    // 2. Copy patterns and models
    copy_directory_contents($patternsSourceDir, $patternsDestDir);
    copy_directory_contents($modelsSourceDir, $modelsDestDir);

    // 3. Generate asset-map.json
    $publicPatterns = array_diff(scandir($patternsDestDir), ['..', '.']);
    $publicModels = array_diff(scandir($modelsDestDir), ['..', '.']);
    $assetMap = [];

    foreach ($publicPatterns as $patternFile) {
        $patternName = pathinfo($patternFile, PATHINFO_FILENAME);
        $foundModel = null;
        foreach ($publicModels as $modelFile) {
            if (pathinfo($modelFile, PATHINFO_FILENAME) === $patternName) {
                $foundModel = $modelFile;
                break;
            }
        }
        if ($foundModel) {
            $assetMap[$patternFile] = $foundModel;
        }
    }

    if (file_put_contents($assetMapPath, json_encode($assetMap, JSON_PRETTY_PRINT)) === false) {
        throw new Exception("No se pudo escribir en el archivo asset-map.json. Verifique los permisos.");
    }

    // 4. Verify the camera parameters file exists in the correct public location.
    if (!file_exists($cameraParaPath)) {
        throw new Exception("Archivo de calibración de cámara (camera_para.dat) no encontrado en la ruta esperada: $cameraParaPath. Por favor, asegúrese de que el archivo exista en esa ubicación.");
    }

    $response['success'] = true;
    $response['message'] = 'Assets de Realidad Aumentada preparados con éxito.';
    
} catch (Exception $e) {
    http_response_code(500);
    $response['message'] = 'Error preparando los assets: ' . $e->getMessage();
    error_log('prepare_ar_assets.php error: ' . $e->getMessage());
}

echo json_encode($response);
?>
