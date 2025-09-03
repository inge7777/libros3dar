<?php
header('Content-Type: application/json');

$result = [
    'success' => true,
    'folders' => [],
    'files' => []
];

// Verificar carpetas críticas
$folders = [
    'assets/models',
    'assets/patterns',
    'assets/images',
    'ARjshithub',
    'ARjshithub/three.js',
    'ARjshithub/aframe',
    'ARjshithub/data',
    'ARjshithub/data/data'
];

foreach ($folders as $folder) {
    $result['folders'][$folder] = [
        'exists' => is_dir($folder),
        'writable' => is_dir($folder) ? is_writable($folder) : false
    ];
    
    // Crear si no existe
    if (!is_dir($folder)) {
        mkdir($folder, 0755, true);
        $result['folders'][$folder]['created'] = true;
    }
}

// Verificar archivos críticos
$files = [
    'ARjshithub/three.js/build/ar-threex.js',
    'ARjshithub/three.js/build/ar.js',
    'ARjshithub/data/data/camera_para.dat'
];

foreach ($files as $file) {
    $result['files'][$file] = file_exists($file);
}

echo json_encode($result);
?>