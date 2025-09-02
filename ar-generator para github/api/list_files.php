<?php
header('Content-Type: application/json');
require_once 'config.php';

$response = [
    'success' => true,
    'images' => [],
    'models' => [],
    'patterns' => []
];

// Helper function to scan a directory and create relative URLs
function scan_directory($real_path, $web_path_prefix) {
    $files = [];
    if (!is_dir($real_path)) {
        return $files;
    }
    // Scandir will list '.' and '..' which we want to ignore
    $items = array_diff(scandir($real_path), array('..', '.'));
    foreach ($items as $item) {
        if (!is_dir($real_path . '/' . $item)) {
            $files[] = [
                'name' => $item,
                'url' => $web_path_prefix . '/' . $item
            ];
        }
    }
    return $files;
}

// Scan for images, models and patterns
$response['images'] = scan_directory(UPLOADS_PATH . '/images', 'uploads/images');
$response['models'] = scan_directory(UPLOADS_PATH . '/models', 'uploads/models');
$response['patterns'] = scan_directory(UPLOADS_PATH . '/patterns', 'uploads/patterns');

echo json_encode($response);
?>
