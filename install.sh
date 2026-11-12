#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Daymark install ==="

# 1. Virtual environment
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

# 2. Python dependencies
echo "Installing Python dependencies..."
"$SCRIPT_DIR/.venv/bin/pip" install --quiet Pillow
"$SCRIPT_DIR/.venv/bin/pip" install --quiet -e "$SCRIPT_DIR"

# 3. Launcher script in ~/.local/bin so the extension can find it
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/daymark" << EOF
#!/usr/bin/env bash
exec "$SCRIPT_DIR/.venv/bin/python" -m daymark "\$@"
EOF
chmod +x "$HOME/.local/bin/daymark"
echo "Launcher installed to ~/.local/bin/daymark"

# 4. Install GNOME extension
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/daymark@daymark.app"
mkdir -p "$EXT_DIR"
cp "$SCRIPT_DIR/gnome-extension/extension.js"  "$EXT_DIR/"
cp "$SCRIPT_DIR/gnome-extension/metadata.json" "$EXT_DIR/"
echo "Extension installed to $EXT_DIR"

# 5. Autostart — start Python app in background at login
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/daymark.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Daymark
Exec=$HOME/.local/bin/daymark --background
Icon=document-edit-symbolic
Comment=Daily scratchpad — starts in background, open via panel icon
X-GNOME-Autostart-enabled=true
EOF
echo "Autostart entry created."

echo ""
echo "=== Done! ==="
echo ""
echo "Next steps:"
echo "  1. Log out and log back in"
echo "     (GNOME Shell must restart to load the extension)"
echo ""
echo "  2. After login, enable the extension:"
echo "     gnome-extensions enable daymark@daymark.app"
echo ""
echo "  3. A pencil icon appears in your top panel (right side)."
echo "     Click it to open Daymark."
