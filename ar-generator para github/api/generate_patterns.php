<?php
header('Content-Type: application/json');
require_once 'config.php';

$response = ['success' => false, 'message' => ''];

try {
    $imagesDir = UPLOADS_PATH . '/images';
    $patternsDir = UPLOADS_PATH . '/patterns';
    $modelsDir = UPLOADS_PATH . '/models';
    $assetsDir = BASE_PATH . '/assets';

    // Crear directorios si no existen
    foreach ([$patternsDir, $assetsDir] as $dir) {
        if (!is_dir($dir)) mkdir($dir, 0755, true);
    }

    $input = json_decode(file_get_contents('php://input'), true);
    $images = $input['images'] ?? [];

    if (empty($images)) {
        throw new Exception('No hay imágenes para procesar');
    }

    $patternsGenerated = [];
    $models = [];

    // Escanear modelos disponibles
    if (is_dir($modelsDir)) {
        $models = array_diff(scandir($modelsDir), ['..', '.']);
    }

    // Generar patrones y registrar
    foreach ($images as $image) {
        $name = pathinfo($image, PATHINFO_FILENAME);
        $pattFile = $name . '.patt';
        
        // Verificar si existe modelo correspondiente
        $foundModel = null;
        foreach ($models as $model) {
            if (pathinfo($model, PATHINFO_FILENAME) === $name) {
                $foundModel = $model;
                break;
            }
        }

        if ($foundModel) {
            // Crear patrón vacío (placeholder)
            $patternContent = "PATTERN\n16 16\n";
            for ($i = 0; $i < 16; $i++) {
                $patternContent .= "255 255 255 255 255 255 255 255 255 255 255 255 255 255 255 255\n";
            }
            
            file_put_contents($patternsDir . '/' . $pattFile, $patternContent);
            $patternsGenerated[] = $pattFile;
        }
    }

    // Generar asset-map.json automáticamente
    $assetMap = [];
    $patterns = array_diff(scandir($patternsDir), ['..', '.']);
    
    foreach ($patterns as $patt) {
        if (pathinfo($patt, PATHINFO_EXTENSION) === 'patt') {
            $name = pathinfo($patt, PATHINFO_FILENAME);
            foreach ($models as $model) {
                if (pathinfo($model, PATHINFO_FILENAME) === $name) {
                    $assetMap[$patt] = $model;
                    break;
                }
            }
        }
    }

    // Copiar archivos a assets/
    foreach ($patterns as $patt) {
        if (pathinfo($patt, PATHINFO_EXTENSION) === 'patt') {
            copy($patternsDir . '/' . $patt, $assetsDir . '/' . $patt);
        }
    }
    
    foreach ($models as $model) {
        if (pathinfo($model, PATHINFO_EXTENSION) === 'glb') {
            copy($modelsDir . '/' . $model, $assetsDir . '/' . $model);
        }
    }

    // Guardar asset-map.json
    file_put_contents($assetsDir . '/asset-map.json', json_encode($assetMap, JSON_PRETTY_PRINT));

    $response['success'] = true;
    $response['message'] = 'Patrones generados y asset-map.json actualizado';
    $response['patterns'] = $patternsGenerated;
    $response['map'] = $assetMap;

} catch (Exception $e) {
    $response['message'] = $e->getMessage();
}

echo json_encode($response);
?>