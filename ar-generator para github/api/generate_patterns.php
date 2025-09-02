<?php
require_once 'config.php';

$response = [
    'success' => false,
    'patterns' => [],
    'message' => ''
];

// --- Verificación de la Librería GD ---
if (!extension_loaded('gd') || !function_exists('gd_info')) {
    $response['message'] = 'Error Crítico: La librería GD de PHP no está instalada o activada en el servidor. Es necesaria para la generación de patrones.';
    http_response_code(500);
    error_log($response['message']);
    echo json_encode($response);
    exit;
}

// --- Lógica de Procesamiento ---
$input = json_decode(file_get_contents('php://input'), true);

if (!isset($input['images']) || !is_array($input['images'])) {
    $response['message'] = 'No se recibió una lista de imágenes válida para procesar.';
    http_response_code(400);
    echo json_encode($response);
    exit;
}

$imagesToProcess = $input['images'];
$patternsDir = UPLOADS_PATH . '/patterns';
$imagesDir = UPLOADS_PATH . '/images';

if (!is_dir($patternsDir)) mkdir($patternsDir, 0777, true);

foreach ($imagesToProcess as $filename) {
    $safeFilename = basename($filename);
    $imagePath = $imagesDir . '/' . $safeFilename;
    $patternName = pathinfo($safeFilename, PATHINFO_FILENAME) . '.patt';
    $patternPath = $patternsDir . '/' . $patternName;

    if (!file_exists($imagePath)) {
        $response['patterns'][] = ['filename' => $patternName, 'status' => 'error', 'detail' => 'Archivo de imagen no encontrado en el servidor.'];
        continue;
    }

    try {
        // --- Proceso de Creación de .patt con GD ---
        
        // 1. Cargar la imagen original
        $imageInfo = getimagesize($imagePath);
        $mime = $imageInfo['mime'];
        $source_image = null;
        if ($mime == 'image/jpeg') {
            $source_image = imagecreatefromjpeg($imagePath);
        } elseif ($mime == 'image/png') {
            $source_image = imagecreatefrompng($imagePath);
        } else {
            throw new Exception("Formato de imagen no soportado: $mime");
        }

        if (!$source_image) throw new Exception("No se pudo cargar la imagen desde $safeFilename");

        // 2. Crear un lienzo de destino de 16x16
        $dest_image = imagecreatetruecolor(16, 16);

        // 3. Redimensionar la imagen original al lienzo de 16x16
        imagecopyresampled($dest_image, $source_image, 0, 0, 0, 0, 16, 16, imagesx($source_image), imagesy($source_image));

        // 4. Convertir a escala de grises
        imagefilter($dest_image, IMG_FILTER_GRAYSCALE);

        // 5. Extraer los valores de los píxeles y construir la matriz del patrón
        $patt_matrix = [];
        for ($y = 0; $y < 16; $y++) {
            $row = [];
            for ($x = 0; $x < 16; $x++) {
                $rgb = imagecolorat($dest_image, $x, $y);
                $gray = ($rgb >> 16) & 0xFF; // En escala de grises, R=G=B, así que solo tomamos un canal.
                $row[] = $gray;
            }
            $patt_matrix[] = $row;
        }

        // 6. Formatear y guardar el archivo .patt
        // El formato ARToolKit .patt repite la matriz 3 veces.
        $patt_content = "";
        for ($i = 0; $i < 3; $i++) {
            foreach ($patt_matrix as $row) {
                // Formatear cada número para que tenga un ancho de 3 caracteres
                $patt_content .= implode(' ', array_map(function($val) { return str_pad($val, 3, ' ', STR_PAD_LEFT); }, $row));
                $patt_content .= "\n";
            }
            if ($i < 2) {
                $patt_content .= "\n";
            }
        }
        
        file_put_contents($patternPath, $patt_content);

        // 7. Limpiar memoria
        imagedestroy($source_image);
        imagedestroy($dest_image);

        if (file_exists($patternPath) && filesize($patternPath) > 0) {
            $response['patterns'][] = [
                'filename' => $patternName,
                'status' => 'ok',
                'detail' => 'Patrón generado con PHP/GD.',
                'url' => 'uploads/patterns/' . $patternName
            ];
        } else {
             throw new Exception("El archivo .patt no se pudo escribir en el disco.");
        }

    } catch (Exception $e) {
        $errorDetail = "Error procesando imagen '$safeFilename': " . $e->getMessage();
        error_log($errorDetail);
        $response['patterns'][] = [
            'filename' => $patternName,
            'status' => 'error',
            'detail' => $errorDetail
        ];
    }
}

$response['success'] = true;
$response['message'] = 'Proceso de generación de patrones finalizado.';
echo json_encode($response);
?>
