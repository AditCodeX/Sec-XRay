@echo off
setlocal EnableDelayedExpansion
title Sec-XRay v1.0.0 Installer

echo ========================================================
echo          Sec-XRay v1.0.0 - Windows Auto-Installer
echo ========================================================
echo.

:: 1. Verifikasi ketersediaan Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [X] ERROR: Python 3 tidak ditemukan!
    echo     Pastikan Python 3.8+ sudah terinstall dan opsi 'Add python.exe to PATH' dicentang.
    echo     Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version') do set PY_VER=%%v
echo [+] Ditemukan: %PY_VER%
echo.

:: 2. Install dependensi Python dan package entrypoint
echo [*] Menginstal dependensi Python dan mendaftarkan console script...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r "%~dp0requirements.txt"
IF %ERRORLEVEL% NEQ 0 (
    echo [!] Gagal menginstal requirements.txt via pip.
    pause
    exit /b 1
)

python -m pip install -e "%~dp0" >nul 2>&1

:: 3. Download Chromium untuk Playwright
echo [*] Mengunduh binary browser Chromium headless...
python -m playwright install chromium
IF %ERRORLEVEL% NEQ 0 (
    echo [!] Gagal mengunduh browser Chromium. Periksa koneksi internet Anda.
    pause
    exit /b 1
)

:: 4. Buat file wrapper sec-xray.bat lokal sebagai fallback
echo [*] Membuat launcher eksekusi global (sec-xray.bat)...
(
echo @echo off
echo python "%%~dp0sec_xray.py" %%*
) > "%~dp0sec-xray.bat"

:: 5. Otomatis daftarkan direktori ini ke User PATH via PowerShell
echo [*] Mendaftarkan Sec-XRay ke Environment PATH Pengguna...
set "TARGET_DIR=%~dp0"
if "%TARGET_DIR:~-1%"=="\" set "TARGET_DIR=%TARGET_DIR:~0,-1%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$targetDir = '%TARGET_DIR%';" ^
    "$userPath = [Environment]::GetEnvironmentVariable('Path', 'User');" ^
    "$paths = ($userPath -split ';') | Where-Object { $_ -ne '' -and (Test-Path $_) };" ^
    "if ($paths -notcontains $targetDir) {" ^
    "    $newPath = ($paths + $targetDir) -join ';';" ^
    "    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User');" ^
    "    Write-Host '[+] SUKSES: Direktori berhasil ditambahkan ke User PATH!' -ForegroundColor Green;" ^
    "} else {" ^
    "    Write-Host '[*] INFO: Direktori sudah terdaftar di User PATH.' -ForegroundColor Cyan;" ^
    "}"

echo.
echo ========================================================
echo [+] INSTALASI SEC-XRAY v1.0.0 SELESAI DENGAN SUKSES!
echo ========================================================
echo.
echo Anda sekarang bisa membuka Terminal / CMD / PowerShell baru
echo di direktori MANAPUN dan langsung memanggil tool dengan:
echo.
echo     sec-xray
echo.
echo Selamat berburu celah keamanan! (Happy Hunting)
echo.
pause
