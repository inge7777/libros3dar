<?php
header('Content-Type: application/json');
require_once 'config.php';

$response = [
    'success' => false,
    'message' => ''
];

try {
    $patternsDir = UPLOADS_PATH . '/patterns';
    $modelsDir = UPLOADS_PATH . '/models';
    $assetsDir = dirname(__DIR__) . '/assets'; // Assumes assets directory is at the root level

    if (!is_dir($assetsDir)) {
        mkdir($assetsDir, 0777, true);
    }

    $assetMapPath = $assetsDir . '/asset-map.json';

    $patterns = array_diff(scandir($patternsDir), array('..', '.'));
    $models = array_diff(scandir($modelsDir), array('..', '.'));

    $assetMap = [];

    foreach ($patterns as $patternFile) {
        $patternName = pathinfo($patternFile, PATHINFO_FILENAME);
        
        // Find a corresponding model file (e.g., marker1.patt -> marker1.glb)
        $foundModel = null;
        foreach ($models as $modelFile) {
            $modelName = pathinfo($modelFile, PATHINFO_FILENAME);
            if ($patternName === $modelName) {
                $foundModel = $modelFile;
                break;
            }
        }

        if ($foundModel) {
            $assetMap[$patternFile] = $foundModel;
        }
    }

    if (file_put_contents($assetMapPath, json_encode($assetMap, JSON_PRETTY_PRINT))) {
        $response['success'] = true;
        $response['message'] = 'Asset map generado con éxito.';
        $response['map'] = $assetMap;
    } else {
        throw new Exception('No se pudo escribir en el archivo asset-map.json. Verifique los permisos.');
    }

} catch (Exception $e) {
    http_response_code(500);
    $response['message'] = 'Error generando el asset map: ' . $e->getMessage();
}

echo json_encode($response);
?>
