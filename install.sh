#!/usr/bin/env bash
set -e

USUARIO=$(whoami)
DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Instalando Center ROG Ally para el usuario: $USUARIO..."

if kpackagetool6 -t Plasma/Applet -l | grep -q "org.ally.center"; then
    kpackagetool6 -t Plasma/Applet -u "$DIR_SCRIPT/org.ally.center"
else
    kpackagetool6 -t Plasma/Applet -i "$DIR_SCRIPT/org.ally.center"
fi

chmod +x "$HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py"

echo "$USUARIO ALL=(ALL) NOPASSWD: /usr/bin/python3 $HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py *" | sudo tee /etc/sudoers.d/ally-center > /dev/null
sudo chmod 440 /etc/sudoers.d/ally-center

echo "==> Reiniciando Plasma..."
systemctl --user restart plasma-plasmashell

echo "¡Listo! Haz clic derecho en tu barra de tareas -> Anadir o gestionar widgets -> Center ROG Ally."
