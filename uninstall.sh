#!/usr/bin/env bash
set -e

echo "==> Desinstalando Center ROG Ally..."

# 1. Detener y eliminar servicio systemd
if systemctl is-enabled --quiet ally-center.service 2>/dev/null; then
    sudo systemctl disable ally-center.service
fi
sudo rm -f /etc/systemd/system/ally-center.service
sudo systemctl daemon-reload

# 2. Eliminar regla sudoers y archivo de estado del sistema
sudo rm -f /etc/sudoers.d/ally-center
sudo rm -f /etc/ally-center.json

# 3. Desinstalar plasmoide de KDE Plasma 6
if kpackagetool6 -t Plasma/Applet -l | grep -q "org.ally.center"; then
    kpackagetool6 -t Plasma/Applet -r org.ally.center
fi

# 4. Eliminar icono personalizado del tema hicolor
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/ally-center.svg"
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# 5. Reiniciar Plasma
echo "==> Reiniciando Plasma..."
systemctl --user restart plasma-plasmashell

echo "¡Desinstalacion completada! Center ROG Ally ha sido eliminado del sistema."
