<?php
header('Content-Type: application/json');
require_once 'config.php';

$response = ['success' => false, 'message' => ''];

try {
    $modelsDir = UPLOADS_PATH . '/models';
    $patternsDir = UPLOADS_PATH . '/patterns';
    $assetsDir = BASE_PATH . '/assets';

    // Crear directorios si no existen
    if (!is_dir($assetsDir)) mkdir($assetsDir, 0755, true);

    // Escanear archivos
    $models = is_dir($modelsDir) ? array_diff(scandir($modelsDir), ['..', '.']) : [];
    $patterns = is_dir($patternsDir) ? array_diff(scandir($patternsDir), ['..', '.']) : [];

    // Copiar archivos a assets/
    foreach ($models as $model) {
        if (pathinfo($model, PATHINFO_EXTENSION) === 'glb') {
            copy($modelsDir . '/' . $model, $assetsDir . '/' . $model);
        }
    }

    foreach ($patterns as $patt) {
        if (pathinfo($patt, PATHINFO_EXTENSION) === 'patt') {
            copy($patternsDir . '/' . $patt, $assetsDir . '/' . $patt);
        }
    }

    // Generar mapa
    $map = [];
    foreach ($patterns as $patt) {
        $name = pathinfo($patt, PATHINFO_FILENAME);
        foreach ($models as $model) {
            if (pathinfo($model, PATHINFO_FILENAME) === $name) {
                $map[$patt] = $model;
                break;
            }
        }
    }

    file_put_contents($assetsDir . '/asset-map.json', json_encode($map, JSON_PRETTY_PRINT));

    $response['success'] = true;
    $response['message'] = 'Mapa actualizado correctamente';
    $response['map'] = $map;

} catch (Exception $e) {
    $response['message'] = $e->getMessage();
}

echo json_encode($response);
?>