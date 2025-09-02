<?php
header('Content-Type: application/json');
require_once 'config.php';

/**
 * Recursively deletes a directory and all of its contents.
 *
 * @param string $dir The directory to delete.
 */
function delete_directory_recursively($dir) {
    if (!is_dir($dir)) {
        return;
    }

    $files = array_diff(scandir($dir), array('.', '..'));
    foreach ($files as $file) {
        $path = "$dir/$file";
        is_dir($path) ? delete_directory_recursively($path) : unlink($path);
    }
    rmdir($dir);
}

$response = [
    'success' => false,
    'message' => 'An unknown error occurred.'
];

try {
    $dirs_to_reset = [
        UPLOADS_PATH . '/images',
        UPLOADS_PATH . '/models',
        UPLOADS_PATH . '/patterns'
    ];

    foreach ($dirs_to_reset as $dir) {
        if (is_dir($dir)) {
            delete_directory_recursively($dir);
        }
        // Recreate the directory after deleting it
        mkdir($dir, 0777, true);
    }

    $response['success'] = true;
    $response['message'] = 'Todos los archivos (imágenes, modelos, patrones) han sido eliminados y el sistema ha sido reiniciado.';
    
} catch (Exception $e) {
    http_response_code(500);
    $response['message'] = 'Error al reiniciar el sistema: ' . $e->getMessage();
}

echo json_encode($response);
?>
