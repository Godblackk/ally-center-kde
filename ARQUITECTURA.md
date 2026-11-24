# Arquitectura Técnica - Center ROG Ally (KDE Plasma 6 + Steam Modo Juego)

> **⚠️ EXCLUSIVO PARA ASUS ROG ALLY / ROG ALLY X:** Documentación técnica de archivos, rutas del kernel de Linux y protocolos para **ASUS ROG Ally (RC71L)** y **ROG Ally X (RC72LA)**.

## 1. Estructura de archivos del proyecto

- **Scripts de instalación/desinstalación**: `install.sh` y `uninstall.sh` gestionan el despliegue del plasmoide, iconos, reglas `sudoers`, integración con Steam CEF y servicios `systemd`.
- **Documentación**: `README.md` (guía de uso e instalación) y `ARQUITECTURA.md` (referencia técnica).
- **Módulos del widget (`org.ally.center/`)**:
  - `metadata.json` y `contents/config/main.xml`: Configuración y persistencia del applet en KDE Plasma 6.
  - `contents/icons/`: Iconos vectoriales SVG del sistema.
  - `contents/scripts/estado.sh`: Lector POSIX ultrarrápido (< 2 ms, sin `sudo`) para telemetría combinando el kernel y `/etc/ally-center.json`.
  - `contents/scripts/ally_center.py`: Backend con privilegios root (vía `sudoers` y `fcntl.flock`) para hardware, RGB y `/etc/ally-center.json`.
  - `contents/scripts/ally_steam_bridge.py`: Demonio de usuario (`systemd --user`) conectado al puerto de depuración CEF de Steam (`localhost:8080`) para integrar el widget en **Configuraciones rápidas (`... → ⚙️`)** del Modo Juego.
  - `contents/ui/main.qml`: Interfaz gráfica desarrollada con QML / Kirigami.

## 2. Rutas del kernel de Linux utilizadas (`estado.sh` / `ally_center.py`)

- **Hardware y energía**: Identificación de modelo en `/sys/devices/virtual/dmi/id/product_name` y estado AC/batería en `/sys/class/power_supply/*/type`.
- **Telemetría de batería (BAT0/BATT)**: Monitoreo de capacidad, estado (`Discharging`, `Charging`, etc.), energía restante, potencia en Watts, tiempo estimado y umbral de carga (`/sys/class/power_supply/BAT0/ o /BATT/`).
- **Rendimiento y TDP (`asus-armoury`)**: 
  - Perfiles ACPI (`/sys/firmware/acpi/platform_profile`).
  - Límites de potencia PL1, PL2 y PL3 para modos *Ahorro*, *Equilibrado*, *Rendimiento* y *Manual* (`/sys/class/firmware-attributes/asus-armoury/attributes/`).
  - Control de CPU Boost (`/sys/devices/system/cpu/cpufreq/boost`).
- **Sensores (`hwmon`)**: Lectura de temperatura APU (`amdgpu` / `k10temp`), consumo energético, RPM de ventiladores y curvas PWM personalizadas (`asus_custom_fan_curve`).
- **Iluminación RGB**: Gestión de anillos LED mediante `ally_center.py` (modos estáticos y dinámicos).
- **Persistencia de arranque y suspensión (`systemd`):** `/etc/ally-center.json` restaurado al iniciar por `/etc/systemd/system/ally-center.service` y al despertar de suspensión/hibernación mediante el hook `/etc/systemd/system-sleep/ally-center` (`ally_center.py boot`).


## 3. Comandos y scripts internos

### Telemetría en tiempo real (`estado.sh`)

| Script | Privilegios | Descripción |
| :--- | :--- | :--- |
| `sh estado.sh` | Usuario (sin `sudo`) | Consulta `/sys/` y `/etc/ally-center.json` en `< 2 ms` para generar un JSON con métricas de hardware (modelo, RPM, temperatura APU, vatios del chip, estado AC, batería y perfiles). |

### Control de hardware (`ally_center.py`)

| Comando | Parámetros | Descripción |
| :--- | :--- | :--- |
| `perfil` | `0`, `1` o `2` | Aplica perfiles ACPI (`low-power`, `balanced`, `performance`) y límites de vatios según la fuente de alimentación. |
| `tdp` | `7..30 [boost_pico]` | Configura el `SPL` y ajusta `SPPT`/`FPPT` según el modo de impulso, respetando topes de `25W` en batería y `30W` en AC. |
| `boost` | `0` o `1` | Activa o desactiva `CPU Boost` vía `cpufreq` y guarda la preferencia en `/etc/ally-center.json`. |
| `bateria` | `0` o `1` | Alterna el límite de carga de la batería `BAT0` entre el 80% (`1`) y el 100% (`0`). |
| `auto` | *(ninguno)* | Devuelve el control térmico de los ventiladores a la BIOS (`pwm1_enable = 2`). |
| `ambos` / `cpu_fan` / `gpu_fan` | `0..100` | Ajustan la velocidad de los ventiladores de forma conjunta o individual, actualizando los modos en la configuración. |
| `guardar_curva` | `v1,v2,...,v8` | Almacena y aplica una curva de ventilación personalizada de 8 puntos en el firmware. |
| `rgb` / `rgb_live` / `rgb_tick` | `modo r g b brillo velocidad` | Gestiona los efectos e iluminación LED (estáticos, efectos con velocidad e indicadores dinámicos con histéresis de 2 °C en temperatura y prioridad verde con cargador AC). |
| `boot` | *(ninguno)* | Empleado por `systemd` durante el arranque para restaurar la última configuración guardada. |

## 4. Integración con Steam Modo Juego y Sincronización Bidireccional (`ally_steam_bridge.py`)

El sistema se integra de forma nativa con **Gamescope / Steam GamepadUI** mediante el protocolo de depuración remota de Chromium Embedded Framework (CEF), prescindiendo de plugins externos:

- **Depuración CEF:** `install.sh` habilita la bandera en el directorio de Steam (`.cef-enable-remote-debugging`) para exponer la interfaz en `http://localhost:8080/json`.
- **Inyección en Configuraciones rápidas:** `ally_steam_bridge.py` (ejecutado por un servicio de `systemd`) se conecta por WebSocket al panel lateral de Steam para añadir una tarjeta de control táctil compatible con el entorno.
- **Estructura en 3 sub-pestañas:**
  - **Telemetría superior:** Muestra modelo, estado de carga (`AC` / `BAT`), RPM, temperaturas, vatios y estimación de autonomía.
  - **TDP:** Permite alternar perfiles de energía, ajustar el vataje mediante barra deslizante (`7W–30W`) y modificar parámetros de impulso (`CPU Boost` y `SPPT/FPPT`).
  - **Ventiladores:** Ofrece modos automático (BIOS), manual con perfiles predefinidos o personalización mediante curva de 8 puntos.
  - **RGB:** Controla patrones lumínicos, selección rápida de colores y niveles de brillo.
- **Sincronización:** Emplea `/etc/ally-center.json` como repositorio central compartido con KDE Plasma (`main.qml`), integrando un sistema de protección anti-rebote (`2.5 s`) durante el ajuste táctil.
