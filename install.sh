#!/usr/bin/env bash
set -e

USUARIO=$(whoami)
DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"

echo "==> Instalando Center ROG Ally para el usuario: $USUARIO..."

if kpackagetool6 -t Plasma/Applet -l | grep -q "org.ally.center"; then
    kpackagetool6 -t Plasma/Applet -u "$DIR_SCRIPT/org.ally.center"
else
    kpackagetool6 -t Plasma/Applet -i "$DIR_SCRIPT/org.ally.center"
fi

mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
cp "$DIR_SCRIPT/org.ally.center/contents/icons/logo.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/ally-center.svg"
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

chmod +x "$HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py"
chmod +x "$HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/estado.sh"

echo "$USUARIO ALL=(ALL) NOPASSWD: /usr/bin/python3 $HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py *" | sudo tee /etc/sudoers.d/ally-center > /dev/null
sudo chmod 440 /etc/sudoers.d/ally-center

printf "[Unit]
Description=Restaurar perfil TDP y ventiladores ROG Ally
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $HOME/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py boot

[Install]
WantedBy=multi-user.target
" | sudo tee /etc/systemd/system/ally-center.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable ally-center.service

echo "==> Reiniciando Plasma..."
systemctl --user restart plasma-plasmashell

echo "¡Listo! Haz clic derecho en tu barra de tareas -> Anadir o gestionar widgets -> Center ROG Ally."
