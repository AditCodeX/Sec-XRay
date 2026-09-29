#!/usr/bin/env bash

set -e

echo "========================================================"
echo "          Sec-XRay v1.0.0 - Linux/macOS Auto-Installer  "
echo "========================================================"
echo ""

# 1. Verifikasi ketersediaan Python 3 & pip3
if ! command -v python3 &> /dev/null; then
    echo "[X] ERROR: python3 tidak ditemukan!"
    echo "    Harap install Python 3.8+ (misal: sudo apt install python3 python3-pip python3-venv)"
    exit 1
fi

if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    echo "[X] ERROR: pip3 tidak ditemukan! Harap install python3-pip."
    exit 1
fi

PY_VER=$(python3 --version)
echo "[+] Ditemukan: $PY_VER"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 2. Install dependensi Python dan package entrypoint
echo "[*] Menginstal dependensi Python dan mendaftarkan console script..."
python3 -m pip install --upgrade pip > /dev/null 2>&1 || true
python3 -m pip install -r "$SCRIPT_DIR/requirements.txt"
python3 -m pip install -e "$SCRIPT_DIR" > /dev/null 2>&1 || true

# 3. Download Chromium untuk Playwright
echo "[*] Mengunduh binary browser Chromium headless..."
python3 -m playwright install chromium

# 4. Buat executable launcher global di ~/.local/bin
echo "[*] Mengonfigurasi executable launcher global..."
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

LAUNCHER="$BIN_DIR/sec-xray"
cat << EOF > "$LAUNCHER"
#!/usr/bin/env bash
python3 "$SCRIPT_DIR/sec_xray.py" "\$@"
EOF
chmod +x "$LAUNCHER"

# 5. Daftarkan ~/.local/bin ke PATH shell user (~/.bashrc, ~/.zshrc)
echo "[*] Memastikan PATH terdaftar di profile shell..."
SHELL_CONFIGS=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile")
PATH_ENTRY='export PATH="$HOME/.local/bin:$PATH"'

for CFG in "${SHELL_CONFIGS[@]}"; do
    if [ -f "$CFG" ]; then
        if ! grep -qs 'HOME/.local/bin' "$CFG"; then
            echo "" >> "$CFG"
            echo "# Sec-XRay Global CLI Path" >> "$CFG"
            echo "$PATH_ENTRY" >> "$CFG"
            echo "[+] Berhasil menambahkan ~/.local/bin ke $CFG"
        fi
    fi
done

# Opsi symlink ke /usr/local/bin jika memiliki hak akses
if [ -w "/usr/local/bin" ]; then
    ln -sf "$LAUNCHER" "/usr/local/bin/sec-xray" 2>/dev/null || true
    echo "[+] Symlink /usr/local/bin/sec-xray dibuat."
fi

echo ""
echo "========================================================"
echo "[+] INSTALASI SEC-XRAY v1.0.0 SELESAI DENGAN SUKSES!"
echo "========================================================"
echo ""
echo "Anda sekarang bisa membuka Terminal baru di direktori MANAPUN"
echo "dan langsung memanggil tool dengan:"
echo ""
echo "    sec-xray"
echo ""
echo "Selamat berburu celah keamanan! (Happy Hunting)"
echo ""
