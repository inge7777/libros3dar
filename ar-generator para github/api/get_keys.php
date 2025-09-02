<?php
require_once 'config.php';

$response = [
    'success' => false,
    'message' => 'No se pudieron obtener las claves.',
    'keys' => []
];

try {
    $pdo = get_pdo();

    // --- Generación de Claves (Funcionalidad Opcional) ---
    // Se activa llamando a /api/get_keys.php?generate=100&app_name=MiApp
    if (isset($_GET['generate'])) {
        $count = filter_var($_GET['generate'], FILTER_VALIDATE_INT);
        $appName = isset($_GET['app_name']) ? htmlspecialchars($_GET['app_name']) : 'generic_app';

        if ($count > 0 && $count <= 5000) { // Límite de seguridad
            $pdo->beginTransaction();
            $stmt = $pdo->prepare(
                "INSERT INTO activaciones (token, app_name, fecha_creacion) VALUES (:token, :app_name, :fecha_creacion)"
            );
            
            $generatedCount = 0;
            for ($i = 0; $i < $count; $i++) {
                // Generar un token único más robusto
                $token = strtoupper(bin2hex(random_bytes(8))); // ej: 1A2B3C4D5E6F7G8H
                $fecha = date('Y-m-d H:i:s');
                
                // El token tiene una restricción UNIQUE, por lo que si hay colisión, fallará.
                // Lo ideal es volver a intentar, pero para este caso, simplemente lo saltamos.
                try {
                    $stmt->execute([
                        ':token' => $token,
                        ':app_name' => $appName,
                        ':fecha_creacion' => $fecha
                    ]);
                    $generatedCount++;
                } catch (PDOException $e) {
                    // Ignorar error de restricción UNIQUE y continuar.
                    if ($e->getCode() !== '23000') {
                        throw $e; // Lanzar otros errores
                    }
                }
            }
            $pdo->commit();
            $response['generation_message'] = "$generatedCount clave(s) nueva(s) generada(s) para la app '$appName'.";
        } else {
             $response['generation_message'] = "La cantidad para generar debe ser un número entre 1 y 5000.";
        }
    }

    // --- Consulta Principal de Claves ---
    $stmt = $pdo->query("SELECT id, token, device_id, fecha_creacion, usado, fecha_uso, app_name FROM activaciones ORDER BY id DESC");
    $keys = $stmt->fetchAll();

    $response['success'] = true;
    $response['message'] = 'Claves obtenidas con éxito.';
    $response['keys'] = $keys;

} catch (Exception $e) {
    if ($pdo && $pdo->inTransaction()) {
        $pdo->rollBack();
    }
    $response['message'] = 'Error de base de datos: ' . $e->getMessage();
    http_response_code(500);
}

echo json_encode($response);
?>
