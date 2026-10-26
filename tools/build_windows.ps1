[CmdletBinding()]
param(
    [ValidateRange(3, 60)]
    [int]$StartupTimeoutSeconds = 12
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$distPath = Join-Path $projectRoot 'dist'
$buildPath = Join-Path $projectRoot 'build'
$exePath = Join-Path $distPath 'daily-knowledge-learning/daily-knowledge-learning.exe'

foreach ($path in @($distPath, $buildPath)) {
    if (Test-Path -LiteralPath $path) {
        $resolvedPath = (Resolve-Path -LiteralPath $path).Path
        if (-not $resolvedPath.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a build path outside the project: $resolvedPath"
        }
        Remove-Item -LiteralPath $resolvedPath -Recurse -Force
    }
}

Write-Host 'Building Windows onedir application...'
$pythonBase = (uv run python -c "import sys; print(sys.base_prefix)").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not locate the Python runtime.' }
$python3Dll = Join-Path $pythonBase 'python3.dll'
if (-not (Test-Path -LiteralPath $python3Dll -PathType Leaf)) {
    throw "Python stable ABI runtime not found: $python3Dll"
}
$buildOriginalPath = $env:PATH
try {
    # Qt 6 uses Windows ICU. A tool's incompatible ICU on PATH must not be bundled.
    $env:PATH = (Join-Path $env:SystemRoot 'System32') + ';' + $buildOriginalPath
    uv run pyinstaller --noconfirm --clean --windowed --onedir `
        --name daily-knowledge-learning --icon assets/daily-learning.ico --paths src `
        --version-file tools/version_info.txt `
        --add-data "assets/daily-learning.ico;assets" --add-binary "$python3Dll;." tools/ui_entry.py
    $buildExitCode = $LASTEXITCODE
} finally {
    $env:PATH = $buildOriginalPath
}
if ($buildExitCode -ne 0) {
    throw "PyInstaller failed with exit code $buildExitCode"
}
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Expected executable was not created: $exePath"
}

$process = $null
try {
    $process = Start-Process -FilePath $exePath -WorkingDirectory (Split-Path -Parent $exePath) -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    $windowReady = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $process.Refresh()
        if ($process.HasExited) {
            throw "Packaged application exited during startup check (exit code $($process.ExitCode))."
        }
        if (-not [string]::IsNullOrWhiteSpace($process.MainWindowTitle)) {
            $windowReady = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $windowReady) {
        throw "Application stayed alive but its main window was not ready: $($process.MainWindowTitle)"
    }
    Write-Host 'Startup check passed: main window title detected and process is alive.'
} finally {
    if ($null -ne $process) {
        $process.Refresh()
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
}

$item = Get-Item -LiteralPath $exePath
Write-Host "Build succeeded: $($item.FullName)"
Write-Host ('EXE size: {0:N0} bytes' -f $item.Length)

$isccPath = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $isccPath -PathType Leaf)) {
    $isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($null -ne $isccCommand) { $isccPath = $isccCommand.Source }
}
if (-not (Test-Path -LiteralPath $isccPath -PathType Leaf)) {
    throw 'Inno Setup 6 is required to create the Windows installer. Install it from https://jrsoftware.org/isinfo.php'
}

$installerScript = Join-Path $PSScriptRoot 'installer.iss'
& $isccPath "/DProjectRoot=$projectRoot" "/DAppVersion=1.0.0" $installerScript
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }

$portableZip = Join-Path $distPath 'daily-knowledge-learning-portable-v1.0.0.zip'
if (Test-Path -LiteralPath $portableZip) {
    Remove-Item -LiteralPath $portableZip -Force
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    (Join-Path $distPath 'daily-knowledge-learning'),
    $portableZip
)
Write-Host "Portable package: $portableZip"
