<?php
header('Content-Type: application/json');
require_once 'config.php';

$response = ['success' => false, 'message' => ''];

try {
    // Directorios a limpiar (solo contenido, no carpetas)
    $dirs = [
        UPLOADS_PATH . '/images',
        UPLOADS_PATH . '/models',
        UPLOADS_PATH . '/patterns',
        BASE_PATH . '/assets'
    ];

    foreach ($dirs as $dir) {
        if (is_dir($dir)) {
            $files = array_diff(scandir($dir), ['..', '.']);
            foreach ($files as $file) {
                $filePath = $dir . '/' . $file;
                if (is_file($filePath)) {
                    unlink($filePath);
                }
            }
        }
    }

    // Crear asset-map.json vacío
    file_put_contents(BASE_PATH . '/assets/asset-map.json', '{}');

    // Recrear directorios si no existen
    foreach ([UPLOADS_PATH . '/images', UPLOADS_PATH . '/models', UPLOADS_PATH . '/patterns', BASE_PATH . '/assets'] as $dir) {
        if (!is_dir($dir)) mkdir($dir, 0755, true);
    }

    $response['success'] = true;
    $response['message'] = 'Sistema reiniciado correctamente (solo archivos limpiados)';

} catch (Exception $e) {
    $response['message'] = $e->getMessage();
}

echo json_encode($response);
?>