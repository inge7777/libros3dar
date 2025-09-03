<?php
header('Content-Type: application/json');
require_once 'config.php';

try {
    $assetsDir = BASE_PATH . '/assets';
    $modelsDir = UPLOADS_PATH . '/models';
    $patternsDir = UPLOADS_PATH . '/patterns';
    
    // Crear directorios si no existen
    if (!is_dir($assetsDir)) mkdir($assetsDir, 0755, true);
    
    // Generar mapa vacío si no hay archivos
    $models = is_dir($modelsDir) ? array_diff(scandir($modelsDir), ['..', '.']) : [];
    $patterns = is_dir($patternsDir) ? array_diff(scandir($patternsDir), ['..', '.']) : [];
    
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
    
    echo json_encode(['success' => true, 'map' => $map]);
    
} catch (Exception $e) {
    echo json_encode(['success' => false, 'message' => $e->getMessage()]);
}
?>