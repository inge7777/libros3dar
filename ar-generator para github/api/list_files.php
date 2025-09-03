<?php
header('Content-Type: application/json');
require_once 'config.php';

function scan_directory($real_path, $web_path_prefix) {
    $files = [];
    if (!is_dir($real_path)) return $files;
    
    foreach (array_diff(scandir($real_path), ['..', '.']) as $item) {
        $full_path = $real_path . '/' . $item;
        if (is_file($full_path)) {
            $files[] = ['name' => $item, 'url' => $web_path_prefix . '/' . $item];
        }
    }
    return $files;
}

echo json_encode([
    'success' => true,
    'images' => scan_directory(UPLOADS_PATH . '/images', 'uploads/images'),
    'models' => scan_directory(UPLOADS_PATH . '/models', 'uploads/models'),
    'patterns' => scan_directory(UPLOADS_PATH . '/patterns', 'uploads/patterns')
]);
?>