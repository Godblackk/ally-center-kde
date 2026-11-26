# 🏗️ Arquitectura Técnica — Center ROG Ally X

Este documento describe la estructura interna, el flujo de datos, las interfaces de hardware del kernel Linux y el mecanismo de sincronización entre el entorno de escritorio **KDE Plasma 6** y **Steam Modo Juego (Gamescope)**.

---

## 1. Estructura de Archivos

```text
ally-center-kde/
├── install.sh                                      # Instalador automático (permisos, sudoers, servicios systemd)
├── uninstall.sh                                    # Desinstalador limpio
├── README.md                                       # Documentación general
├── ARQUITECTURA.md                                 # Documentación técnica (este archivo)
└── org.ally.center/
    ├── metadata.json                               # Metadatos del plasmoid de KDE Plasma 6
    └── contents/
        ├── ui/
        │   ├── main.qml                            # Interfaz gráfica nativa de KDE Plasma 6 (QML)
        │   └── i18n.js                             # Diccionario multi-idioma compartido (ES, EN, PT, FR, DE, JA, ZH)
        └── scripts/
            ├── ally_center.py                      # Backend privilegiado (escritura en sysfs y persistencia JSON)
            ├── estado.sh                           # Monitor rápido de sensores hwmon y estado actual
            └── ally_steam_bridge.py                # Demonio puente WebSocket CEF + vigilante de modos/energía
```
---

## 2. Interfaces del Kernel (`sysfs` y `hwmon`)

El backend (`ally_center.py`) y el monitor (`estado.sh`) interactúan directamente con los nodos expuestos por el driver `asus-armoury` y los controladores LED/ACPI de la **ROG Ally X**:

* **Perfiles de Energía ACPI:** `/sys/firmware/acpi/platform_profile` (`quiet`, `balanced`, `performance`).
* **Límites de Potencia (TDP):** `/sys/class/firmware-attributes/asus-armoury/attributes/`
  * `ppt_pl1_spl/current_value` (Límite sostenido SPL: `7W–30W`).
  * `ppt_pl2_sppt/current_value` (Impulso corto SPPT).
  * `ppt_fppt/current_value` (Pico instantáneo FPPT).
  * `cpu_boost/current_value` (Turbo Boost de CPU: `0` / `1`).
* **Cuidado de Batería:** `/sys/class/power_supply/BAT0/charge_control_end_threshold` (`80` o `100`).
* **Curvas de Ventilación (8 puntos `30°C–100°C`):**
  * CPU: `/sys/class/firmware-attributes/asus-armoury/attributes/fan_curve_cpu/`
  * GPU: `/sys/class/firmware-attributes/asus-armoury/attributes/fan_curve_gpu/`
* **Iluminación RGB de Joysticks:** `/sys/class/leds/ally:rgb:joystick_rings/multi_intensity` y `/sys/class/leds/ally:rgb:joystick_rings/brightness`.
* **Telemetría (`estado.sh`):** Lecturas directas desde `/sys/class/hwmon/` (RPM de ventiladores, temperatura de APU, consumo instantáneo en vatios y porcentaje de batería).
---

## 3. Flujo de Datos, Modos y Vigilante Anti-Override

1. **Persistencia Centralizada (`/etc/ally-center.json`):**
   * Almacena tanto el estado activo global como el diccionario `perfiles_modo` con claves separadas para `"desktop"` y `"game"`, gobernado por el indicador booleano `sync_modos`.
   * Cuando `sync_modos` es `true` (**Sync ON**), cualquier cambio en escritorio o en juego actualiza ambos perfiles en espejo. Cuando es `false` (**Por Modo**), cada entorno lee y guarda su propia configuración independiente.

2. **Detección Dual de Entorno (`ally_steam_bridge.py`):**
   * El demonio `systemd --user` consulta periódicamente el endpoint CEF de Steam (`http://127.0.0.1:8080/json`) buscando el target `QuickAccess` (Big Picture / QAM) **y** verifica la presencia del proceso `gamescope` en `/proc`.
   * Esto evita falsos positivos al regresar de **Modo Juego (Gamescope) → Escritorio (Plasma)**, donde Steam permanece corriendo en segundo plano (`-silent`) para gestionar *Steam Input* sin interfaz Big Picture activa.

3. **Vigilante de Integridad y Orden de Arranque (`vigilar_perfil_activo`):**
   * El servicio `ally-steam-bridge.service` declara `After=plasma-powerdevil.service` para asegurar que la aplicación del perfil de escritorio ocurra después de que KDE Plasma inicialice su gestor de energía.
   * Adicionalmente, la tarea asíncrona `vigilar_perfil_activo(modo)` supervisa cada `1.5s` los valores reales de `ppt_pl1_spl` y `platform_profile` en el kernel; si `PowerDevil` o `UPower` sobrescriben los límites al iniciar sesión o al conectar/desconectar el cargador AC, el puente re-aplica `/etc/ally-center.json` automáticamente.
