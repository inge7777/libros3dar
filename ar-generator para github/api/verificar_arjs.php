<?php
header('Content-Type: application/json');

// Rutas críticas de AR.js
$criticalPaths = [
    'ARjshithub/three.js/build/ar-threex.js',
    'ARjshithub/three.js/build/ar.js',
    'ARjshithub/three.js/examples/vendor/three.js/build/three.min.js',
    'ARjshithub/three.js/examples/vendor/three.js/GLTFLoader.js',
    'ARjshithub/data/data/camera_para.dat',
    'ARjshithub/aframe/build/aframe-ar.js',
    'ARjshithub/aframe/build/aframe-ar-nft.js'
];

// Verificar existencia
$missing = [];
$existing = [];

foreach ($criticalPaths as $path) {
    if (file_exists($path)) {
        $existing[] = $path;
    } else {
        $missing[] = $path;
    }
}

// Verificar carpetas principales
$folders = [
    'ARjshithub/three.js',
    'ARjshithub/aframe',
    'ARjshithub/data',
    'assets/models',
    'assets/patterns',
    'assets/images'
];

$folderStatus = [];
foreach ($folders as $folder) {
    $folderStatus[$folder] = [
        'exists' => is_dir($folder),
        'writable' => is_writable($folder)
    ];
}

echo json_encode([
    'success' => true,
    'missing' => $missing,
    'existing' => $existing,
    'folders' => $folderStatus,
    'base_path' => getcwd()
]);
?>