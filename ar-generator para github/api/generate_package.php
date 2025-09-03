<?php
header('Content-Type: application/json');

$input = json_decode(file_get_contents('php://input'), true);
$appName = $input['appName'] ?? 'MiAppAR';
$packageName = $input['packageName'] ?? 'com.miapp.ar';
$files = $input['files'] ?? [];

$distDir = __DIR__ . "/../dist/$packageName";
if (!is_dir($distDir)) mkdir($distDir, 0777, true);

// Copiar assets
$assetsDist = $distDir . '/assets';
if (!is_dir($assetsDist)) mkdir($assetsDist, 0777, true);
copy(__DIR__ . '/../assets/asset-map.json', $assetsDist . '/asset-map.json');
copy(__DIR__ . '/../ar.html', $distDir . '/index.html');

// Copiar modelos y patrones
shell_exec("cp -r " . __DIR__ . "/../uploads/* $assetsDist/");

echo json_encode(['success' => true, 'packagePath' => "/dist/$packageName"]);
?>