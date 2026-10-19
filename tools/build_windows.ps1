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
uv run pyinstaller --noconfirm --clean --windowed --onedir `
    --name daily-knowledge-learning --paths src tools/ui_entry.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Expected executable was not created: $exePath"
}

$process = $null
try {
    $process = Start-Process -FilePath $exePath -WorkingDirectory (Split-Path -Parent $exePath) -PassThru
    if (-not $process.WaitForExit($StartupTimeoutSeconds * 1000)) {
        Write-Host "Startup check passed: process remained alive for $StartupTimeoutSeconds seconds."
    } else {
        throw "Packaged application exited during startup check (exit code $($process.ExitCode))."
    }
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
