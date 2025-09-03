<?php
header('Content-Type: application/json');

function downloadArJs() {
    $arjsUrl = 'https://github.com/AR-js-org/AR.js/archive/refs/heads/master.zip';
    $tempFile = tempnam(sys_get_temp_dir(), 'arjs_');
    
    // Descargar
    $ch = curl_init($arjsUrl);
    $fp = fopen($tempFile, 'w+');
    curl_setopt($ch, CURLOPT_FILE, $fp);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    curl_exec($ch);
    curl_close($ch);
    fclose($fp);
    
    // Extraer
    $zip = new ZipArchive();
    if ($zip->open($tempFile) === TRUE) {
        $zip->extractTo('./');
        $zip->close();
        
        // Renombrar carpeta
        if (is_dir('AR.js-master')) {
            rename('AR.js-master', 'ARjshithub');
        }
        
        unlink($tempFile);
        return ['success' => true, 'message' => 'AR.js descargado y extraído'];
    }
    
    return ['success' => false, 'message' => 'Error al extraer ZIP'];
}

$result = downloadArJs();
echo json_encode($result);
?>