#!/usr/bin/env bash
set -e

USUARIO=$(whoami)
if [ "$USUARIO" = "root" ]; then
    echo "Error: Ejecuta ./uninstall.sh como tu usuario normal (sin sudo)."
    exit 1
fi

echo "==> Desinstalando Center ROG Ally..."

# 1. Detener y eliminar el servicio del puente de Modo Juego (usuario)
systemctl --user disable --now ally-steam-bridge.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/ally-steam-bridge.service"
systemctl --user daemon-reload 2>/dev/null || true

# 2. Eliminar archivos de depuración CEF en Steam (nativo y Flatpak)
rm -f "$HOME/.local/share/Steam/.cef-enable-remote-debugging" \
      "$HOME/.steam/steam/.cef-enable-remote-debugging" \
      "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/.cef-enable-remote-debugging"

# 3. Detener y eliminar el servicio de restauración al arranque (sistema)
sudo systemctl disable --now ally-center.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/ally-center.service
sudo rm -f /etc/systemd/system-sleep/ally-center /usr/lib/systemd/system-sleep/ally-center
sudo systemctl daemon-reload

# 4. Eliminar permisos sudoers e icono
sudo rm -f /etc/sudoers.d/ally-center
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/ally-center.svg"
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# 5. Desinstalar el plasmoide de KDE Plasma 6
if kpackagetool6 -t Plasma/Applet -l | grep -q "org.ally.center"; then
    kpackagetool6 -t Plasma/Applet -r org.ally.center
fi

echo "==> Reiniciando Plasma..."
systemctl --user restart plasma-plasmashell 2>/dev/null || true

echo "¡Center ROG Ally desinstalado por completo!"
