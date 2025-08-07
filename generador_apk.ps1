#Requires -Version 5.1
<#
.SYNOPSIS
  Generador robusto de APK para Capacitor con nombre e ícono personalizados.
#>

param (
    [Parameter(Mandatory = $true)][string]$PaqueteNombre,
    [Parameter(Mandatory = $true)][string]$PortadaPath,
    [string]$Claves,
    [Parameter(Mandatory = $true)][string]$ProjectDir, # Nuevo parámetro: Ruta del proyecto Capacitor (ej: D:\libros3dar2\capacitor)
    [Parameter(Mandatory = $true)][string]$AndroidDir  # Nuevo parámetro: Ruta de la carpeta Android (ej: D:\libros3dar2\capacitor\android)
)

$ErrorActionPreference = "Stop"

$BaseDir       = "D:\libros3dar2" # Se mantiene para otras rutas base si es necesario
$PackageDir    = Join-Path $BaseDir "paquetes"
$WWWDir        = Join-Path $ProjectDir "www" # Ahora usa el $ProjectDir pasado como parámetro
$OutputDir     = Join-Path $BaseDir "output-apk"
$LogDir        = Join-Path $OutputDir "logs"
$SdkManager    = "D:\androidstudio\Sdk\cmdline-tools\latest\bin\sdkManager.bat" # Corregido a .bat

function Log-Message {
    param([string]$msg)
    if (-not $global:LogFile) {
        $global:LogFile = Join-Path $LogDir ("log_ps_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
    }
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $line = "[$timestamp] $msg"
    try { $line | Out-File -FilePath $global:LogFile -Encoding UTF8 -Append } catch {}
    Write-Output $line # Esto asegura que el mensaje también se envíe a la salida estándar para la GUI
}

function Check-AndroidLicenses {
    Log-Message "Verificando licencias del Android SDK..."
    if (-not (Test-Path $SdkManager)) {
        Log-Message "ERROR: No se encontró sdkmanager en $SdkManager."
        throw "No se encontró sdkmanager."
    }
    try {
        # Capturar la salida de sdkmanager --licenses
        $tempOutput = Join-Path $LogDir "sdkmanager_output.txt"
        $tempError = Join-Path $LogDir "sdkmanager_error.txt"
        $process = Start-Process -FilePath $SdkManager -ArgumentList "--licenses" -NoNewWindow -PassThru -RedirectStandardOutput $tempOutput -RedirectStandardError $tempError
        $process | Wait-Process -Timeout 60 -ErrorAction Stop

        if ($process.ExitCode -ne 0) {
            $errorContent = Get-Content $tempError -Raw -ErrorAction SilentlyContinue
            Log-Message "ERROR: Fallo al verificar licencias. Código: $($process.ExitCode). Detalles: $errorContent"
            throw "Fallo al verificar licencias."
        }
        $licenseOutput = Get-Content $tempOutput -Raw -ErrorAction SilentlyContinue

        # Si hay licencias no aceptadas, intentar aceptarlas
        if ($licenseOutput -match "license.*not accepted") {
            Log-Message "Licencias no aceptadas. Intentando aceptarlas..."
            $acceptInput = Join-Path $LogDir "sdkmanager_input.txt"
            "y`n" * 10 | Out-File $acceptInput -Encoding ASCII # Simula presionar 'y' varias veces
            $acceptProcess = Start-Process -FilePath $SdkManager -ArgumentList "--licenses" -NoNewWindow -PassThru -RedirectStandardInput $acceptInput -RedirectStandardOutput (Join-Path $LogDir "sdkmanager_accept_output.txt") -RedirectStandardError (Join-Path $LogDir "sdkmanager_accept_error.txt")
            $acceptProcess | Wait-Process -Timeout 60 -ErrorAction Stop

            if ($acceptProcess.ExitCode -ne 0) {
                $acceptError = Get-Content (Join-Path $LogDir "sdkmanager_accept_error.txt") -Raw -ErrorAction SilentlyContinue
                Log-Message "ERROR: Fallo al aceptar licencias. Código: $($acceptProcess.ExitCode). Detalles: $acceptError"
                throw "Fallo al aceptar licencias."
            }
            Log-Message "Licencias aceptadas."
        } else {
            Log-Message "Licencias verificadas."
        }
    } catch {
        Log-Message "ERROR al verificar/aceptar licencias: $($_.Exception.Message)"
        throw
    } finally {
        # Limpiar archivos temporales
        Remove-Item (Join-Path $LogDir "sdkmanager_*.txt") -ErrorAction SilentlyContinue
    }
}

# Crear carpeta de logs si no existe
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
Log-Message "========= Inicio generador APK ========="

try {
    # Validar que las rutas pasadas existen
    if (-not (Test-Path $AndroidDir)) { throw "No se encontró carpeta Android: $AndroidDir" }
    if (-not (Test-Path $PortadaPath)) { throw "No se encontró portada: $PortadaPath" }

    # Validar Java
    $javaHome = $env:JAVA_HOME
    if (-not $javaHome -or -not (Test-Path "$javaHome\bin\java.exe")) {
        # Si JAVA_HOME no está configurado o no es válido, intentar con la ruta por defecto de Android Studio
        $javaHome = "D:\androidstudio\jbr"
        if (Test-Path "$javaHome\bin\java.exe") {
            Log-Message "Java detectado en ruta predeterminada de Android Studio."
            $env:JAVA_HOME = $javaHome
            $env:Path = "$javaHome\bin;$env:Path" # Añadir Java al PATH de la sesión actual
        } else {
            # Si tampoco se encuentra en la ruta por defecto, verificar si está en el PATH del sistema
            & java -version > $null 2>&1 # Intenta ejecutar java y redirige la salida
            if ($LASTEXITCODE -ne 0) { throw "Java no encontrado o inaccesible en PATH." }
            Log-Message "Java detectado via PATH."
        }
    } else {
        Log-Message "Java detectado en JAVA_HOME: $javaHome"
    }

    # Verificar licencias del Android SDK
    Check-AndroidLicenses

    # Limpiar carpeta www (en el ProjectDir)
    if (Test-Path $WWWDir) { Remove-Item "$WWWDir\*" -Recurse -Force -ErrorAction SilentlyContinue }
    else { New-Item -ItemType Directory -Path $WWWDir | Out-Null }
    Log-Message "Carpeta www limpiada."

    # Limpiar carpeta de build de Android (en el AndroidDir)
    $AndroidBuildDir = Join-Path $AndroidDir "app\build"
    if (Test-Path $AndroidBuildDir) { Remove-Item $AndroidBuildDir -Recurse -Force -ErrorAction SilentlyContinue }
    Log-Message "Build Android limpiado."

    # Copiar paquete a www
    $SourcePkg = Join-Path $PackageDir $PaqueteNombre
    if (-not (Test-Path $SourcePkg)) { throw "No existe el paquete especificado: $SourcePkg" }
    # Usar robocopy para una copia robusta, sin mostrar la salida en la consola principal
    & robocopy $SourcePkg $WWWDir /E /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
    Log-Message "Paquete copiado a www."

    # Ejecutar npx cap sync
    Push-Location $ProjectDir # Cambiar al directorio del proyecto Capacitor
    try {
        $npxCmd = "D:\nodejs\nodejsinstalado\npx.cmd"
        if (-not (Test-Path $npxCmd)) { $npxCmd = "npx" } # Fallback si la ruta específica no existe
        Log-Message "Ejecutando npx cap sync..."
        # Redirigir la salida de npx cap sync al log y a la consola
        & $npxCmd cap sync *>&1 | ForEach-Object { Log-Message "[npx] $_" }
        if ($LASTEXITCODE -ne 0) { throw "Error ejecutando 'npx cap sync'." }
        Log-Message "'npx cap sync' ejecutado exitosamente."
    } finally { Pop-Location } # Volver al directorio original

    # Build gradle
    $gradleOutputLogFile = Join-Path $LogDir ("gradle_output_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
    $gradleErrorLogFile = Join-Path $LogDir ("gradle_error_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log") # Nuevo archivo para errores
    
    Log-Message "---- INICIANDO BUILD GRADLE ----"
    Log-Message "Log de salida de Gradle se guardará en: $gradleOutputLogFile"
    Log-Message "Log de errores de Gradle se guardará en: $gradleErrorLogFile"

    Push-Location $AndroidDir # Cambiar al directorio de Android para ejecutar gradlew.bat
    try {
        # Definir el comando y sus argumentos
        $gradleExecutable = ".\gradlew.bat"
        $gradleArguments = @("clean", "assembleDebug", "--console=plain", "--info")

        Log-Message "Ejecutando comando Gradle: $gradleExecutable $gradleArguments"
        
        # Iniciar el proceso de Gradle directamente y redirigir su salida a archivos separados
        $process = Start-Process -FilePath $gradleExecutable -ArgumentList $gradleArguments -NoNewWindow -PassThru -RedirectStandardOutput $gradleOutputLogFile -RedirectStandardError $gradleErrorLogFile
        
        # Esperar a que el proceso de Gradle termine.
        $process.WaitForExit(1800000) # Esperar hasta 30 minutos (1800000 ms)

        # Capturar el código de salida del proceso
        $gradleExitCode = $process.ExitCode

        if (-not $process.HasExited) {
            $process.Kill()
            throw "Timeout de 30 minutos alcanzado para el build de Gradle. Terminando proceso."
        }
        
        # Leer el contenido del log de salida estándar de Gradle y enviarlo a la GUI
        $fullGradleOutputContent = ""
        if (Test-Path $gradleOutputLogFile) {
            $fullGradleOutputContent = Get-Content $gradleOutputLogFile -Raw -ErrorAction SilentlyContinue
            Log-Message "--- Salida estándar de Gradle ---"
            $fullGradleOutputContent.Split("`n") | ForEach-Object { Log-Message "[gradle-out] $_" }
            Log-Message "--- Fin de salida estándar de Gradle ---"
        } else {
            Log-Message "ADVERTENCIA: No se encontró el archivo de log de salida estándar de Gradle: $gradleOutputLogFile"
        }

        # Leer el contenido del log de errores de Gradle y enviarlo a la GUI
        $fullGradleErrorContent = ""
        if (Test-Path $gradleErrorLogFile) {
            $fullGradleErrorContent = Get-Content $gradleErrorLogFile -Raw -ErrorAction SilentlyContinue
            if ($fullGradleErrorContent) { # Solo mostrar si hay contenido de error
                Log-Message "--- Salida de errores de Gradle ---"
                $fullGradleErrorContent.Split("`n") | ForEach-Object { Log-Message "[gradle-err] $_" }
                Log-Message "--- Fin de salida de errores de Gradle ---"
            }
        } else {
            Log-Message "ADVERTENCIA: No se encontró el archivo de log de errores de Gradle: $gradleErrorLogFile"
        }

        if ($gradleExitCode -ne 0) {
            Log-Message "ERROR: Build de Gradle fallido. Código de salida: $($gradleExitCode)."
            throw "Build fallido. Consulta los logs para más detalles."
        }
        Log-Message "Build completado exitosamente."

        $apkRoot = Join-Path $AndroidDir "app\build\outputs\apk\debug"
        $apkFile = Get-ChildItem -Path $apkRoot -Filter "app-debug.apk" -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $apkFile) {
            throw "No se encontró el archivo app-debug.apk."
        }
        Log-Message "APK generado: $($apkFile.FullName)"

        $apkDestDir = Join-Path $OutputDir $PaqueteNombre
        if (-not (Test-Path $apkDestDir)) { New-Item -ItemType Directory -Path $apkDestDir | Out-Null }
        $apkDest = Join-Path $apkDestDir "$PaqueteNombre-debug.apk"
        Copy-Item $apkFile.FullName $apkDest -Force
        Log-Message "APK copiado: $apkDest"

        if ($Claves -and $Claves.Trim().Length -gt 0) {
            $claveFile = Join-Path $apkDestDir "claves-activacion.txt"
            $Claves.Split(",") | Set-Content -Path $claveFile -Encoding UTF8
            Log-Message "Archivo de claves creado en $claveFile"
        }

        Log-Message "Proceso finalizado correctamente para paquete '$PaqueteNombre'."

    } catch {
        Log-Message "ERROR en build Gradle: $($_.Exception.Message)"
        throw
    } finally { Pop-Location } # Volver al directorio original

} catch {
    Log-Message ("ERROR CRÍTICO EN SCRIPT: " + $_.Exception.Message)
    exit 1
} finally {
    # Limpiar los archivos de log temporales de Gradle al final
    Remove-Item $gradleOutputLogFile -ErrorAction SilentlyContinue
    Remove-Item $gradleErrorLogFile -ErrorAction SilentlyContinue
    Log-Message "========= Fin generador APK ========="
}