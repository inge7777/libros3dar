<?php
require_once 'config.php';

// --- Funciones de Ayuda ---

/**
 * Ejecuta un comando y devuelve un array con el éxito, la salida y el código de retorno.
 * @param string $command El comando a ejecutar.
 * @return array
 */
function execute_command($command) {
    $output = [];
    $return_code = 0;
    // La redirección 2>&1 es crucial para capturar los mensajes de error de stderr.
    exec($command . ' 2>&1', $output, $return_code);
    return [
        'success' => $return_code === 0,
        'output' => implode("\n", $output),
        'return_code' => $return_code
    ];
}

// --- Lógica Principal ---

$response = [
    'success' => false,
    'message' => 'Petición de compilación inválida.',
    'log' => ''
];

$input = json_decode(file_get_contents('php://input'), true);

if (!$input || !isset($input['packagePath'])) {
    echo json_encode($response);
    exit;
}

$packagePath = $input['packagePath'];

// --- Verificación de Seguridad ---
// Resuelve la ruta real y comprueba que esté dentro del directorio de paquetes permitido.
$realPackagePath = realpath($packagePath);
$realPackagesRoot = realpath(PACKAGES_PATH);

if ($realPackagePath === false || strpos($realPackagePath, $realPackagesRoot) !== 0 || !is_dir($realPackagePath)) {
    $response['message'] = 'Ruta de paquete no válida o insegura.';
    http_response_code(400);
    echo json_encode($response);
    exit;
}

try {
    // --- Comandos de Compilación ---
    // El servidor web (Laragon/Apache) debe tener acceso a `npx` en su PATH.
    // Esto puede requerir configuración del sistema.

    // 1. Sincronizar los assets web con el proyecto nativo.
    $syncCommand = 'cd "' . $realPackagePath . '" && npx cap sync android';
    $syncResult = execute_command($syncCommand);

    if (!$syncResult['success']) {
        // Lanza una excepción para ser capturada por el bloque catch.
        throw new Exception("Error en 'npx cap sync android'.\n" . $syncResult['output']);
    }

    // 2. Compilar el APK usando Gradle.
    $androidProjectPath = $realPackagePath . '/android';
    
    // El comando varía ligeramente entre Windows y Linux/macOS.
    $gradleCommand = 'gradlew.bat assembleDebug'; // Por defecto para Windows
    if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
        // En Linux/macOS, gradlew necesita permisos de ejecución.
        $gradlewPath = $androidProjectPath . '/gradlew';
        if(is_file($gradlewPath)) {
            chmod($gradlewPath, 0755); // Asegurar permisos de ejecución
        }
        $gradleCommand = './gradlew assembleDebug';
    }

    $buildCommand = 'cd "' . $androidProjectPath . '" && ' . $gradleCommand;
    $buildResult = execute_command($buildCommand);

    if (!$buildResult['success']) {
        throw new Exception("Error en la compilación de Gradle ('assembleDebug').\n" . $buildResult['output']);
    }

    // 3. Localizar el APK generado.
    $apkName = 'app-debug.apk';
    $apkPath = $realPackagePath . '/android/app/build/outputs/apk/debug/' . $apkName;

    if (!file_exists($apkPath)) {
        throw new Exception("La compilación pareció tener éxito, pero no se encontró el archivo APK en la ruta esperada: " . $apkPath);
    }

    // 4. Éxito: Preparar la respuesta.
    $webApkPath = '/packages/' . basename($realPackagePath) . '/android/app/build/outputs/apk/debug/' . $apkName;
    
    $response['success'] = true;
    $response['message'] = 'APK compilado con éxito.';
    $response['apkPath'] = $webApkPath; // Ruta relativa para el enlace de descarga.
    $response['log'] = "SYNC OK: " . $syncResult['output'] . "\n\nBUILD OK: " . $buildResult['output'];

} catch (Exception $e) {
    // Log del error en el servidor para depuración profunda
    error_log("Error en build_apk.php para el paquete '$realPackagePath': " . $e->getMessage());

    // Capturar cualquier error lanzado y ponerlo en la respuesta.
    $response['message'] = 'Falló el proceso de compilación.';
    $response['log'] = $e->getMessage();
    http_response_code(500); // Internal Server Error
}

echo json_encode($response);
?>
