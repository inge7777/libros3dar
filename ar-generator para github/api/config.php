<?php
// Configuración para Laragon - Generador AR LibrosDAR - v2 Corregida
date_default_timezone_set('America/Bogota');

// --- Rutas del Sistema ---
// ¡CORREGIDO! BASE_PATH ahora apunta a la raíz del proyecto (ar-generator), no a /api.
define('BASE_PATH', dirname(__DIR__)); 
define('UPLOADS_PATH', BASE_PATH . '/uploads');
define('PACKAGES_PATH', BASE_PATH . '/packages');
define('TEMP_PATH', BASE_PATH . '/temp');
define('DATABASE_PATH', BASE_PATH . '/database');
define('BACKEND_DB', DATABASE_PATH . '/activaciones.db');

// --- Rutas de Herramientas Externas (¡IMPORTANTE! AJUSTAR A TU SISTEMA) ---
// ¡CORREGIDO! Todas las rutas de herramientas externas están centralizadas aquí.
define('BASE_3D_AR', 'F:/linux/3d-AR');
define('BLENDER_PATH', 'F:/linux/blender/blender-4.5.1-windows-x64/blender.exe');
define('CAPACITOR_TEMPLATE', BASE_3D_AR . '/capacitor-template');
define('PATT_GENERATOR_EXE', 'F:\\linux\\3d-AR\\nft-creator\\pattern-generator.exe');

// Crear directorios necesarios al iniciar
foreach ([UPLOADS_PATH, UPLOADS_PATH . '/images', UPLOADS_PATH . '/models', UPLOADS_PATH . '/patterns', PACKAGES_PATH, TEMP_PATH, DATABASE_PATH] as $dir) {
    if (!is_dir($dir)) { mkdir($dir, 0755, true); }
}

// --- Funciones de Utilidad ---

function get_pdo() {
    static $pdo = null;
    if ($pdo !== null) return $pdo;
    try {
        $pdo = new PDO("sqlite:" . BACKEND_DB);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
        $pdo->exec("CREATE TABLE IF NOT EXISTS activaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, device_id TEXT, fecha_creacion TEXT NOT NULL, usado INTEGER DEFAULT 0, fecha_uso TEXT, app_name TEXT);");
        return $pdo;
    } catch (PDOException $e) {
        http_response_code(500);
        error_log("Error de base de datos: " . $e->getMessage());
        die(json_encode(['success' => false, 'message' => 'Error de conexión a la base de datos.']));
    }
}

function limpiar_nombre($nombre) {
    $nombre = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $nombre);
    $nombre = preg_replace('/[^a-zA-Z0-9_.-]/', '', $nombre); // Permitir puntos y guiones
    return strtolower(substr($nombre, 0, 50));
}

function ejecutar_comando($comando, $directorio = null) {
    $directorioAnterior = getcwd();
    if ($directorio && is_dir($directorio)) chdir($directorio);
    $output = []; $returnCode = 0;
    exec($comando . ' 2>&1', $output, $returnCode);
    if ($directorio) chdir($directorioAnterior);
    return ['success' => $returnCode === 0, 'output' => implode("\n", $output), 'return_code' => $returnCode];
}

function copiar_recursivo($src, $dst) {
    if (!is_dir($src)) return false;
    $dir = opendir($src);
    if (!$dir) return false;
    if (!is_dir($dst)) mkdir($dst, 0755, true);
    while (($file = readdir($dir)) !== false) {
        if (($file != '.') && ($file != '..')) {
            if (is_dir($src . '/' . $file)) {
                copiar_recursivo($src . '/' . $file, $dst . '/' . $file);
            } else {
                copy($src . '/' . $file, $dst . '/' . $file);
            }
        }
    }
    closedir($dir);
    return true;
}
?>
