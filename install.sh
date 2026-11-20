#!/usr/bin/env bash
set -e

USUARIO=$(whoami)
if [ "$USUARIO" = "root" ]; then
    echo "Error: Ejecuta ./install.sh como tu usuario normal (sin sudo). El script pedira sudo cuando lo necesite."
    exit 1
fi

DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Instalando Center ROG Ally para el usuario: $USUARIO..."

if kpackagetool6 -t Plasma/Applet -l | grep -q "org.ally.center"; then
    kpackagetool6 -t Plasma/Applet -u "$DIR_SCRIPT/org.ally.center"
else
    kpackagetool6 -t Plasma/Applet -i "$DIR_SCRIPT/org.ally.center"
fi

mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
cp "$DIR_SCRIPT/org.ally.center/contents/icons/logo.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/ally-center.svg"
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

chmod +x "$HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/"* 2>/dev/null || true

echo "$USUARIO ALL=(ALL) NOPASSWD: /usr/bin/python3 $HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py *" | sudo tee /etc/sudoers.d/ally-center > /dev/null
sudo chmod 440 /etc/sudoers.d/ally-center

printf "[Unit]
Description=Restaurar perfil TDP y ventiladores ROG Ally
After=multi-user.target power-profiles-daemon.service

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 8
ExecStart=/usr/bin/python3 $HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py boot
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
" | sudo tee /etc/systemd/system/ally-center.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable ally-center.service

# Instalar dependencia de websockets para el puente de Modo Juego
if ! python3 -c "import websockets" 2>/dev/null; then
    if command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm --needed python-websockets 2>/dev/null || true
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-websockets 2>/dev/null || true
    fi
    python3 -m pip install --user --break-system-packages websockets 2>/dev/null || true
fi

# Habilitar debugging CEF oficial en Steam (nativo y Flatpak)
mkdir -p "$HOME/.local/share/Steam"
touch "$HOME/.local/share/Steam/.cef-enable-remote-debugging"
[ -d "$HOME/.steam/steam" ] && touch "$HOME/.steam/steam/.cef-enable-remote-debugging"
[ -d "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam" ] && touch "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/.cef-enable-remote-debugging"

# Crear y activar servicio systemd de usuario para el puente en segundo plano
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/ally-steam-bridge.service" << EOF
[Unit]
Description=Center ROG Ally X - Puente Modo Juego (Steam CEF)
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_steam_bridge.py
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now ally-steam-bridge.service

echo "==> Reiniciando Plasma..."
systemctl --user restart plasma-plasmashell 2>/dev/null || true

echo "¡Listo! Haz clic derecho en tu barra de tareas -> Anadir o gestionar widgets -> Center ROG Ally."

