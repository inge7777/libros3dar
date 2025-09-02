<?php
require_once 'config.php';

$response = [
    'success' => false,
    'message' => 'Petición inválida.',
    'files' => []
];

// Validar que se recibieron archivos y un tipo
if (!isset($_FILES['files']) || !isset($_POST['type'])) {
    $response['message'] = 'No se recibieron archivos o no se especificó el tipo.';
    echo json_encode($response);
    exit;
}

$fileType = $_POST['type'];
if ($fileType !== 'image' && $fileType !== 'model') {
    $response['message'] = 'Tipo de archivo no válido. Debe ser "image" o "model".';
    echo json_encode($response);
    exit;
}

// Determinar el directorio de destino
$targetSubDir = $fileType === 'image' ? 'images' : 'models';
$targetDir = UPLOADS_PATH . '/' . $targetSubDir;

// Crear directorio si no existe
if (!is_dir($targetDir) && !mkdir($targetDir, 0777, true)) {
    $response['message'] = "Error: No se pudo crear el directorio de subida en '$targetDir'. Verifica los permisos.";
    http_response_code(500);
    echo json_encode($response);
    exit;
}

$uploadedFiles = $_FILES['files'];
$successfulUploads = [];
$errorMessages = [];

// Procesar cada archivo subido
for ($i = 0; $i < count($uploadedFiles['name']); $i++) {
    $fileName = basename($uploadedFiles['name'][$i]);
    $targetFilePath = $targetDir . '/' . $fileName;

    if ($uploadedFiles['error'][$i] === UPLOAD_ERR_OK) {
        if (move_uploaded_file($uploadedFiles['tmp_name'][$i], $targetFilePath)) {
            // Guardar la información del archivo subido con éxito
            $successfulUploads[] = [
                'name' => $fileName,
                'path' => $targetFilePath,
                'url' => "/uploads/$targetSubDir/$fileName" // Ruta relativa para acceso web si es necesario
            ];
        } else {
            $errorMessages[] = "No se pudo mover el archivo '$fileName'.";
        }
    } else {
        // Mapear código de error a mensaje
        switch ($uploadedFiles['error'][$i]) {
            case UPLOAD_ERR_INI_SIZE:
                $errorMessages[] = "El archivo '$fileName' excede el tamaño máximo permitido por el servidor.";
                break;
            case UPLOAD_ERR_FORM_SIZE:
                $errorMessages[] = "El archivo '$fileName' excede el tamaño máximo permitido en el formulario.";
                break;
            case UPLOAD_ERR_PARTIAL:
                $errorMessages[] = "El archivo '$fileName' se subió solo parcialmente.";
                break;
            case UPLOAD_ERR_NO_FILE:
                $errorMessages[] = "No se subió ningún archivo con el nombre '$fileName'.";
                break;
            default:
                $errorMessages[] = "Error desconocido al subir '$fileName'.";
                break;
        }
    }
}

// Preparar la respuesta final
if (!empty($successfulUploads)) {
    $response['success'] = true;
    $response['message'] = count($successfulUploads) . ' archivo(s) subido(s) con éxito.';
    $response['files'] = $successfulUploads;
    if (!empty($errorMessages)) {
        $response['message'] .= ' Sin embargo, algunos archivos fallaron: ' . implode(', ', $errorMessages);
    }
} else {
    $response['message'] = 'Ningún archivo se pudo subir. Errores: ' . implode(', ', $errorMessages);
}

echo json_encode($response);
?>
