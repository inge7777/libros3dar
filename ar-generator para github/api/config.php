<?php
date_default_timezone_set('America/Bogota');

// Rutas absolutas para Laragon
define('BASE_PATH', dirname(__DIR__));
define('UPLOADS_PATH', BASE_PATH . '/uploads');
define('PACKAGES_PATH', BASE_PATH . '/packages');
define('TEMP_PATH', BASE_PATH . '/temp');
define('DATABASE_PATH', BASE_PATH . '/database');
define('BACKEND_DB', DATABASE_PATH . '/activaciones.db');

// Herramientas externas
define('BASE_3D_AR', 'F:/linux/3d-AR');
define('BLENDER_PATH', 'F:/linux/blender/blender-4.5.1-windows-x64/blender.exe');
define('PATT_GENERATOR_EXE', 'F:/linux/3d-AR/nft-creator/pattern-generator.exe');

// Crear carpetas si no existen
foreach ([UPLOADS_PATH, UPLOADS_PATH . '/images', UPLOADS_PATH . '/models', UPLOADS_PATH . '/patterns', PACKAGES_PATH, TEMP_PATH, DATABASE_PATH] as $dir) {
    if (!is_dir($dir)) mkdir($dir, 0755, true);
}

function get_pdo() {
    static $pdo = null;
    if ($pdo !== null) return $pdo;
    try {
        $pdo = new PDO("sqlite:" . BACKEND_DB);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->exec("CREATE TABLE IF NOT EXISTS activaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            device_id TEXT,
            fecha_creacion TEXT NOT NULL,
            usado INTEGER DEFAULT 0,
            fecha_uso TEXT,
            app_name TEXT
        );");
        return $pdo;
    } catch (PDOException $e) {
        http_response_code(500);
        die(json_encode(['success' => false, 'message' => 'Error de base de datos']));
    }
}
?>