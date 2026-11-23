# Center ROG Ally (KDE Plasma 6 + Steam Modo Juego)

> **⚠️ EXCLUSIVO PARA ASUS ROG ALLY / ROG ALLY X:** Diseñado **únicamente** para consolas **ASUS ROG Ally (RC71L)** y **ROG Ally X (RC72LA)** en Linux mediante controladores del kernel específicos de ASUS (`asus-armoury`, `asus_custom_fan_curve`, HID/LED). No es compatible con Steam Deck, Lenovo Legion Go u otros dispositivos.

Centro de control nativo para **ASUS ROG Ally** y **ROG Ally X** en Linux (**KDE Plasma 6** y **Steam Modo Juego / Gamescope**).

## Características principales

- **Detección automática de hardware:** Identifica el modelo exacto y el estado de alimentación (`AC` / `BAT` con porcentaje).
- **Telemetría en tiempo real:** Monitorea RPM de ventiladores, temperatura de la APU (°C), consumo del chip (W) y telemetría de batería (`BAT0`: Watts, tiempo restante y potencia de carga).
- **Perfiles de ASUS y TDP dinámico:** Incluye perfiles *Ahorro (13W)*, *Equilibrado (17W)* y *Rendimiento*, además de límite TDP Manual (`7W–30W`) sincronizado con Boost Pico y cuidado de batería (80%).
- **Control de ventiladores:** Modos *Automático*, *Manual* (Silencioso, Equilibrado, Turbo) y *Curva Personalizada* de 8 puntos.
- **Iluminación RGB:** Modos dinámicos (Color Fijo, Temperatura APU, Nivel de Batería, Hora del Día) con control de brillo.
- **Integración con Steam Modo Juego:** Tarjeta táctil en las configuraciones rápidas (`... → ⚙️`) vía CEF (`ally_steam_bridge.py`), dividida en sub-pestañas (*TDP* | *Ventiladores* | *RGB*).
- **Iconos dinámicos y persistencia:** Iconos de barra de tareas según el perfil activo y servicio `systemd` para guardar ajustes en `/etc/ally-center.json`.

## Arquitectura del sistema

El proyecto utiliza una arquitectura desacoplada donde **KDE Plasma 6** y el **Modo Juego de Steam** comparten un backend y estado persistente en tiempo real:

1. **Interfaz KDE Plasma 6 (`contents/ui/main.qml`):** Plasmoide nativo QML/Kirigami para el panel de escritorio con control de energía, ventiladores y RGB.
2. **Puente Steam Modo Juego (`contents/scripts/ally_steam_bridge.py`):** Servicio de usuario (`systemd --user`) que se conecta vía WebSocket al depurador CEF de Steam (`localhost:8080`) e inyecta una tarjeta táctil compacta (`TDP` | `Ventiladores` | `RGB`) en las **Configuraciones rápidas (`... → ⚙️`)**, sin requerir Decky Loader.
3. **Backend de Hardware (`ally_center.py` y `estado.sh`):** Lee y aplica cambios de hardware (sensores en `/sys/class/hwmon`, `asus-armoury`, `cpufreq`, `BAT0`) mediante bloqueo exclusivo (`flock`) persistiendo en `/etc/ally-center.json`.
4. **Sincronización (`/etc/ally-center.json` + `ally-center.service`):** Logra sincronización bidireccional y restauración automática al arrancar.

## Instalación rápida

1. Clona el repositorio y ejecuta el instalador en KDE Plasma:
   ```bash
   git clone https://github.com/Godblackk/ally-center-kde.git
   cd ally-center-kde
   ./install.sh
   ```
2. Introduce tu contraseña (`sudo`) para configurar permisos y servicios.
3. Haz **clic derecho** en la barra de tareas de KDE → **Añadir o gestionar widgets** → selecciona **Center ROG Ally**.

## ¿Qué configura automáticamente `./install.sh`?

- **Widget de Plasma 6:** Instala `org.ally.center` mediante `kpackagetool6`.
- **Permisos sin contraseña:** Crea `/etc/sudoers.d/ally-center` para ajustar hardware sin pedir `sudo`.
- **Persistencia:** Configura `ally-center.service` y el puente de Steam (`ally-steam-bridge.service`).

## Actualización y desinstalación

- **Actualizar:** `cd ~/ally-center-kde && git pull && ./install.sh`
- **Desinstalar:** `cd ~/ally-center-kde && ./uninstall.sh`

## Compatibilidad (ASUS ROG Ally / ROG Ally X)

- **CachyOS / Arch Linux / EndeavourOS (KDE Plasma 6):** Soporte nativo completo.
- **Bazzite / SteamOS (KDE Plasma 6):** Compatible (evita solapar con *Handheld Daemon* en Bazzite; reejecuta `./install.sh` tras grandes actualizaciones de SteamOS).
- **GNOME:** No compatible.
