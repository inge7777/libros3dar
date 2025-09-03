<?php
header('Content-Type: application/json');

$folders = [
    'assets/models',
    'assets/patterns',
    'assets/images',
    'ARjshithub/data/data'
];

$created = [];
foreach ($folders as $folder) {
    if (!is_dir($folder)) {
        mkdir($folder, 0755, true);
        $created[] = $folder;
    }
}

// Copiar camera_para.dat si no existe
if (!file_exists('ARjshithub/data/data/camera_para.dat')) {
    $source = 'ARjshithub/data/camera_para.dat';
    $dest = 'ARjshithub/data/data/camera_para.dat';
    if (file_exists($source)) {
        copy($source, $dest);
    }
}

echo json_encode([
    'success' => true,
    'created' => $created,
    'message' => 'Estructura reparada'
]);
?>