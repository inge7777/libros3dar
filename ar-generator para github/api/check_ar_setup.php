<?php
error_reporting(E_ALL);
ini_set('display_errors', 1);
header('Content-Type: text/plain; charset=UTF-8');

function check_file($path, $label) {
    echo "Verificando $label... ";
    if (file_exists($path)) {
        echo "[OK] Encontrado en: $path\n";
        return true;
    } else {
        echo "[ERROR] FALTA en: $path\n";
        return false;
    }
}

function check_dir($path, $label) {
    echo "Verificando directorio $label... ";
    if (is_dir($path)) {
        $file_count = count(array_diff(scandir($path), array('.', '..')));
        echo "[OK] Encontrado con $file_count archivos.\n";
        return true;
    } else {
        echo "[ERROR] FALTA directorio en: $path\n";
        return false;
    }
}

echo "==== Diagnóstico del Entorno de Realidad Aumentada ====\n\n";

$projectRoot = dirname(__DIR__);
$assetsDir = $projectRoot . '/assets';
$patternsDir = $assetsDir . '/patterns';
$modelsDir = $assetsDir . '/models';
$dataDir = $projectRoot . '/data';

$all_ok = true;

if (!check_file($assetsDir . '/asset-map.json', "asset-map.json")) $all_ok = false;
if (!check_file($dataDir . '/camera_para.dat', "camera_para.dat")) $all_ok = false;
if (!check_dir($patternsDir, "assets/patterns")) $all_ok = false;
if (!check_dir($modelsDir, "assets/models")) $all_ok = false;

echo "\n--- Resumen ---\n";
if ($all_ok) {
    echo "¡TODO LISTO! La estructura de archivos para la RA parece ser correcta.\n";
    echo "Si la RA aún no funciona, el problema podría estar en los permisos de los archivos o en la configuración del servidor web.\n";
} else {
    echo "FALTAN ARCHIVOS O DIRECTORIOS. Por favor, ejecuta el script 'prepare_ar_assets.php' para intentar solucionar el problema.\n";
    echo "Si después de ejecutar el preparador el problema persiste, verifica los permisos de escritura en las carpetas 'assets' y 'data'.\n";
}

echo "\n--- Prueba de Acceso HTTP ---\n";
$protocol = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' || $_SERVER['SERVER_PORT'] == 443) ? "https://" : "http://";
$host = $_SERVER['HTTP_HOST'];
// Attempt to determine the base path if in a subdirectory
$script_name = $_SERVER['SCRIPT_NAME'];
$base_path = str_replace('/api/check_ar_setup.php', '', $script_name);

$url = $protocol . $host . $base_path . "/assets/asset-map.json";
echo "Intentando acceder a: $url\n";

// Use cURL for a more reliable check
$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 5);
curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($http_code == 200) {
    echo "[OK] El archivo asset-map.json es accesible vía web (HTTP 200).\n";
} else {
    echo "[ERROR] No se pudo acceder a asset-map.json vía web. Código de respuesta HTTP: $http_code. Revisa la configuración de tu servidor (ej. .htaccess) y los permisos de la carpeta 'assets'.\n";
}
?>
