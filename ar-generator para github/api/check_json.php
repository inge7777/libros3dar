<?php
header('Content-Type: application/json');
$path = __DIR__ . '/../assets/asset-map.json';
$exists = file_exists($path);
$content = $exists ? file_get_contents($path) : 'No existe';

echo json_encode([
    'exists' => $exists,
    'size' => $exists ? filesize($path) : 0,
    'content' => $content,
    'valid_json' => $exists ? json_decode($content) !== null : false
]);
?>