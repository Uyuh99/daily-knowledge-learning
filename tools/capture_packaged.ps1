$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

$exe = "dist\daily-knowledge-learning\daily-knowledge-learning.exe"
$out = "test-output\packaged-window.png"

$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 12
$proc = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
if (-not $proc) { throw "packaged exe exited early" }
$hwnd = $proc.MainWindowHandle
"title=[$($proc.MainWindowTitle)] hwnd=$hwnd responding=$($proc.Responding)"
if ($hwnd -eq 0) { throw "no main window handle" }

[void][Win32]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 800

$rect = New-Object Win32+RECT
[void][Win32]::GetWindowRect($hwnd, [ref]$rect)
$w = $rect.Right - $rect.Left
$h = $rect.Bottom - $rect.Top
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $gfx.GetHdc()
[void][Win32]::PrintWindow($hwnd, $hdc, 2)
$gfx.ReleaseHdc($hdc)
$gfx.Dispose()
$bmp.Save((Join-Path (Get-Location) $out), [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
"saved $out  ${w}x${h}"

Stop-Process -Id $p.Id -Force
