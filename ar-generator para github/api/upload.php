<?php
require_once 'config.php';

$response = ['success' => false, 'message' => 'Petición inválida'];

if (!isset($_FILES['files']) || !isset($_POST['type'])) {
    echo json_encode($response);
    exit;
}

$type = $_POST['type'];
$dir = $type === 'image' ? '/images' : '/models';
$targetDir = UPLOADS_PATH . $dir;

if (!is_dir($targetDir)) mkdir($targetDir, 0755, true);

$uploaded = [];
for ($i = 0; $i < count($_FILES['files']['name']); $i++) {
    $name = basename($_FILES['files']['name'][$i]);
    $tmp = $_FILES['files']['tmp_name'][$i];
    $dest = $targetDir . '/' . $name;
    
    if (move_uploaded_file($tmp, $dest)) {
        $uploaded[] = $name;
    }
}

echo json_encode(['success' => true, 'files' => $uploaded]);
?>