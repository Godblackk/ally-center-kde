# 🏗️ Arquitectura Técnica — Center ROG Ally / Ally X

Este documento describe el diseño interno, los protocolos de comunicación con el hardware y el flujo de servicios en segundo plano de **Center ROG Ally / Ally X**.

---

## 1. Visión General del Sistema

El proyecto está dividido en tres capas desacopladas para garantizar seguridad, bajo consumo de recursos y compatibilidad tanto en **KDE Plasma 6** (Modo Escritorio) como en **SteamOS / Gamescope** (Modo Juego):

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           CAPA DE PRESENTACIÓN                          │
│                                                                         │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐ │
│   │   Plasmoid KDE Plasma 6       │   │   Steam Gaming Mode (QAM)     │ │
│   │   (main.qml + i18n.js)        │   │   (Inyección CEF HTML/JS)     │ │
│   └───────────────┬───────────────┘   └───────────────┬───────────────┘ │
└───────────────────┼───────────────────────────────────┼─────────────────┘
                    │                                   │
                    │  Plasma DataSource / Executable   │  WebSocket (127.0.0.1:8080)
                    ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        CAPA DE PUENTE Y SERVICIOS                       │
│                                                                         │
│   ally_steam_bridge.py (systemd --user)                                 │
│   • Detecta estado de Gamescope / Steam Big Picture                     │
│   • Inyecta pestaña nativa en QuickAccess y captura mando (A/B/D-Pad)   │
│   • Lee telemetría en tiempo real (APU, batería, temperaturas, RPM)     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    │  sudo /usr/bin/python3 (sin contraseña)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     CAPA PRIVILEGIADA DE HARDWARE                       │
│                                                                         │
│   ally_center.py (Python 3)                                             │
│   • Lee y escribe atributos sysfs (asus-armoury / hwmon)                │
│   • Envía tramas HID crudas por /dev/hidraw* (RGB Joysticks)            │
│   • Persiste estado en /etc/ally-center.json                            │
│   • Ejecuta vigilante de perfil activo y restauración en boot/resume    │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       KERNEL LINUX (≥ 6.13) & FIRMWARE                  │
│   /sys/class/firmware-attributes/asus-armoury/ · /dev/hidraw* · ACPI    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Interfaces de Kernel y Hardware (`ally_center.py`)

### 2.1. Detección de Modelo (`detectar_modelo`)
Lee `/sys/devices/virtual/dmi/id/product_name` para identificar automáticamente la consola y ajustar sus límites seguros de TDP:
* **`RC72LA` (ROG Ally X):** Rango TDP de `7W` a `30W` (con boost SPPT/FPPT hasta `35W`).
* **`RC71L` (ROG Ally Z1 / Z1 Extreme):** Rango TDP de `7W` a `30W` ajustado a las especificaciones térmicas de la primera generación.

### 2.2. Perfiles de Energía, TDP, Boost y Batería (`sysfs`)
* **Perfil ACPI:** `/sys/firmware/acpi/platform_profile` (`quiet`, `balanced`, `performance`).
* **Límites PPT (`asus-armoury`):**
  * **SPL (Sostenido):** `/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl1_spl/current_value`
  * **SPPT (Boost 2 min):** `/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl2_sppt/current_value`
  * **FPPT (Boost 10 seg):** `/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl3_fppt/current_value`
* **CPU Turbo Boost:** `/sys/devices/system/cpu/cpufreq/boost` (`1` activo, `0` inactivo).
* **Cuidado de Batería (80%):** `/sys/class/power_supply/BAT0/charge_control_end_threshold` (`80` o `100`).

### 2.3. Curvas Térmicas de Ventiladores (`asus_custom_fan_curve`)
Localiza dinámicamente el nodo `hwmon` cuyo atributo `name` corresponde a `asus_custom_fan_curve`:
* **Control independiente:** `pwm1` controla el ventilador de **CPU** y `pwm2` el de **GPU**.
* **Modos soportados:**
  * `auto`: Deshabilita la curva manual (`pwm1_enable = 2`, `pwm2_enable = 2`) devolviendo el control al firmware.
  * `manual`: Escribe una curva plana de 8 puntos (`[pct] * 8`) con `pwmX_enable = 1`. Soporta porcentajes vinculados (`vincular_fans: true`) o independientes (`cpu_pct` y `gpu_pct`).
  * `curva`: Escribe 8 pares `(temperatura °C, velocidad %)` en `pwmX_auto_point1_temp`..`8` y `pwmX_auto_point1_pwm`..`8`.

### 2.4. Iluminación RGB Directa por HID (`/dev/hidraw*`)
En lugar de depender exclusivamente de nodos LED de `sysfs`, `ally_center.py` localiza el dispositivo HID de los joysticks inspeccionando `UEVENT` en `/sys/class/hidraw/hidraw*/device/uevent`:
* **IDs soportados:** `00000B05:00001B4C` (**ROG Ally X**) y `00000B05:00001ABE` (**ROG Ally**).
* **Protocolo de paquetes:** Envía tramas binarias de 64 bytes con cabecera ASUS Aura (`0x5A, 0xB3, ...`) para aplicar color RGB, brillo (0–100 %) y efectos nativos por hardware (`fijo`, `respiracion`, `ciclos`, `arcoiris`, `pulso`), seguidas de la trama de confirmación (`0x5A, 0xB4` / `0x5A, 0xB5`).
---

## 3. Puente con Steam Gaming Mode (`ally_steam_bridge.py`)

### 3.1. Inyección vía CEF (Chromium Embedded Framework)
Steam en modo *Big Picture / Gamescope* expone una interfaz de depuración local en `http://127.0.0`. El servicio de usuario `ally-steam-bridge.service` realiza los siguientes pasos:
1. Consulta los targets activos buscando la ventana `QuickAccess` (el menú lateral QAM que se despliega con el botón `···`).
2. Abre una conexión WebSocket persistente contra el `webSocketDebuggerUrl` de `QuickAccess`.
3. Inyecta un contenedor aislado (`#ally-center-qam-root`) con estilos encapsulados y un puente de mensajería bidireccional (`console.debug("ALLY_CMD:...")`) que comunica los eventos de la interfaz hacia Python sin abrir puertos TCP externos adicionales.

### 3.2. Navegación 100 % Nativa con Mando
Para evitar conflictos con el sistema de foco espacial de SteamUI (`GamepadUI`), el script inyectado implementa su propia máquina de estados de navegación:
* **Interceptación selectiva de eventos:** Captura teclas/botones de mando (`ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`, `Enter` / `A`, `Escape` / `Backspace` / `B`) solo cuando la pestaña **Ally Center** está visible y activa.
* **Jerarquía de 2 niveles (Sección → Control):**
  * **Nivel 0 (Lista de secciones):** `Arriba / Abajo` desplaza el foco entre bloques (*Perfiles, TDP, Ventiladores, Curva, RGB, Estadísticas*). Pulsar `A` entra al bloque; pulsar `B` cierra el panel completo.
  * **Nivel 1 (Interior de sección):** `Izquierda / Derecha` navega entre botones internos o ajusta sliders; pulsar `A` aplica el preset/color seleccionado manteniendo el foco en su sitio para confirmación visual; pulsar `B` regresa al Nivel 0.

---

## 4. Persistencia, Vigilante y Servicios `systemd`

### 4.1. Almacenamiento Centralizado (`/etc/ally-center.json`)
Toda modificación realizada desde el plasmoid de KDE o desde el QAM de Steam actualiza atómicamente `/etc/ally-center.json`, guardando:
* Perfil ACPI activo, valores `spl`, `sppt`, `fppt` y estado de `boost` / `bateria_80`.
* Modo de ventilador (`auto`, `manual`, `curva`), estado `vincular_fans`, porcentajes (`fan_pct`, `cpu_pct`, `gpu_pct`) y los 8 puntos de la curva térmica.
* Modo RGB, color `[R, G, B]` y nivel de brillo.

### 4.2. Servicios Activos
* **`ally-center-restore.service` (Sistema):** Se ejecuta al iniciar el sistema (`multi-user.target`) y al despertar de suspensión (`post` en `systemd-sleep`) llamando a `ally_center.py restaurar` para reaplicar toda la configuración guardada (incluyendo ventiladores independientes si `vincular_fans` es `false`).
* **`ally-steam-bridge.service` (Usuario):** Demonio ligero que mantiene viva la integración con el QAM de Steam y ejecuta el bucle de telemetría.
* **Vigilante de Perfil Activo (`vigilar`):** Supervisa cada 1.5 segundos que eventos externos del sistema operativo (como conectar o desconectar el cargador USB-C) no alteren el perfil ACPI ni los límites TDP definidos por el usuario.

---

## 5. Modelo de Seguridad y Permisos (`sudoers`)

Para evitar ejecutar interfaces gráficas o servicios web con privilegios de superusuario (`root`), el proyecto aplica el **principio de mínimo privilegio**:
* Tanto el plasmoid de KDE como `ally_steam_bridge.py` corren completamente bajo el usuario normal sin privilegios.
* El script `install.sh` crea una regla estricta en `/etc/sudoers.d/ally-center`:
  ```text
  usuario ALL=(ALL) NOPASSWD: /usr/bin/python3 /home/usuario/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py *
  ```
* `ally_center.py` valida y sanea todos los argumentos numéricos (rangos seguros de vatios, porcentajes PWM mínimos del 25 % y valores RGB `0–255`) antes de escribir en cualquier nodo del kernel.
