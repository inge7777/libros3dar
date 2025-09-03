<?php
header('Content-Type: application/json');

$rutas = [
    'ARjshithub/three.js/build/ar-threex.js',
    'ARjshithub/three.js/build/ar.js',
    'ARjshithub/data/data/camera_para.dat',
    'ARjshithub/three.js/examples/vendor/three.js/build/three.min.js',
    'ARjshithub/three.js/examples/vendor/three.js/GLTFLoader.js',
    'ARjshithub/aframe/build/aframe-ar.js'
];

$resultado = [];
foreach ($rutas as $ruta) {
    $resultado[$ruta] = file_exists('../' . $ruta) ? '✅ Existe' : '❌ No existe';
}

echo json_encode([
    'success' => true,
    'verificacion' => $resultado
]);
?>