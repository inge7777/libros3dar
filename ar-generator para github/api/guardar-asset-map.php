<?php
// api/guardar-asset-map.php
$input = json_decode(file_get_contents('php://input'), true);
if ($input) {
    file_put_contents(__DIR__ . '/../assets/asset-map.json', json_encode($input, JSON_PRETTY_PRINT));
    echo json_encode(['success' => true]);
} else {
    echo json_encode(['success' => false, 'message' => 'Datos inválidos']);
}