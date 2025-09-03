<?php
// api/generar-asset-map.php
header('Content-Type: application/json');

$baseDir = __DIR__ . '/..';
$modelsDir = $baseDir . '/assets/models';
$patternsDir = $baseDir . '/assets/patterns';

$map = [];

if (!is_dir($modelsDir) || !is_dir($patternsDir)) {
    echo json_encode([]);
    exit;
}

$models = glob("$modelsDir/*.glb");
foreach ($models as $model) {
    $modelName = basename($model);
    $patternName = str_replace('.glb', '.patt', $modelName);
    $patternPath = "$patternsDir/$patternName";
    
    if (file_exists($patternPath)) {
        $map[$patternName] = $modelName;
    }
}

file_put_contents("$baseDir/assets/asset-map.json", json_encode($map, JSON_PRETTY_PRINT));
echo json_encode($map);