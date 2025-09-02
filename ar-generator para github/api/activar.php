<?php
require_once 'config.php';

// El script de activación debe devolver un JSON simple que la app pueda interpretar.
$response = [
    'status' => 'error', // Puede ser 'success' o 'error'
    'message' => 'Petición de activación inválida.'
];

// Se espera que la app móvil envíe los datos como POST.
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    $response['message'] = 'Método no permitido. Se requiere POST.';
    http_response_code(405); // Method Not Allowed
    echo json_encode($response);
    exit;
}

// Obtener datos POST (ya sea como json o form-data)
$input = [];
if (strpos($_SERVER['CONTENT_TYPE'], 'application/json') !== false) {
    $input = json_decode(file_get_contents('php://input'), true);
} else {
    $input = $_POST;
}

if (!isset($input['token']) || !isset($input['device_id'])) {
    $response['message'] = 'Faltan los parámetros requeridos: "token" y "device_id".';
    http_response_code(400); // Bad Request
    echo json_encode($response);
    exit;
}

$token = trim($input['token']);
$deviceId = trim($input['device_id']);

if (empty($token) || empty($deviceId)) {
    $response['message'] = 'El token y el device_id no pueden estar vacíos.';
     http_response_code(400);
    echo json_encode($response);
    exit;
}

try {
    $pdo = get_pdo();

    // 1. Buscar el token en la base de datos
    $stmt = $pdo->prepare("SELECT * FROM activaciones WHERE token = :token");
    $stmt->execute([':token' => $token]);
    $keyRecord = $stmt->fetch();

    if (!$keyRecord) {
        // El token proporcionado no existe
        $response['message'] = 'Token no válido.';
    } else {
        // El token existe, ahora se comprueba su estado
        if ($keyRecord['usado'] == 1) {
            // El token ya fue utilizado
            if ($keyRecord['device_id'] === $deviceId) {
                // Es el mismo dispositivo verificando de nuevo, lo cual es correcto.
                $response['status'] = 'success';
                $response['message'] = 'Dispositivo verificado y activado previamente.';
            } else {
                // Un dispositivo diferente intenta usar un token ya reclamado
                $response['message'] = 'Este token ya ha sido reclamado por otro dispositivo.';
            }
        } else {
            // 2. El token es válido y no ha sido usado. Se procede a la activación.
            $updateStmt = $pdo->prepare(
                "UPDATE activaciones SET usado = 1, device_id = :device_id, fecha_uso = :fecha_uso WHERE id = :id"
            );
            
            $updateSuccess = $updateStmt->execute([
                ':device_id' => $deviceId,
                ':fecha_uso' => date('Y-m-d H:i:s'),
                ':id' => $keyRecord['id']
            ]);

            if ($updateSuccess) {
                $response['status'] = 'success';
                $response['message'] = 'Aplicación activada con éxito.';
            } else {
                $response['message'] = 'Error al actualizar el estado del token.';
                http_response_code(500);
            }
        }
    }

} catch (Exception $e) {
    $response['message'] = 'Error interno del servidor durante la activación.';
    // En un entorno de producción, se registraría el error en un log.
    // error_log('Error en activar.php: ' . $e->getMessage());
    http_response_code(500);
}

echo json_encode($response);
?>
