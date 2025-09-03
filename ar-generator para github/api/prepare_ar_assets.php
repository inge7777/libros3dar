<?php
header('Content-Type: application/json; charset=UTF-8');
require_once 'config.php';

$response = ['success' => false, 'message' => 'Error desconocido'];

try {
    $patternsDir = UPLOADS_PATH . '/patterns';
    $modelsDir = UPLOADS_PATH . '/models';
    $assetsDir = BASE_PATH . '/assets';
    
    foreach ([$assetsDir, $assetsDir . '/patterns', $assetsDir . '/models'] as $dir) {
        if (!is_dir($dir)) mkdir($dir, 0755, true);
    }
    
    // Copiar archivos
    shell_exec("cp -r $patternsDir/* $assetsDir/patterns/");
    shell_exec("cp -r $modelsDir/* $assetsDir/models/");
    
    // Generar asset-map.json
    $patterns = array_diff(scandir($patternsDir), ['..', '.']);
    $models = array_diff(scandir($modelsDir), ['..', '.']);
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
    
    if (!file_exists(BASE_PATH . '/data/camera_para.dat')) {
        throw new Exception('Coloca camera_para.dat en /data/');
    }
    
    $response['success'] = true;
    $response['message'] = 'Assets preparados correctamente';
    
} catch (Exception $e) {
    $response['message'] = $e->getMessage();
}

echo json_encode($response);
?>