# Arquitectura Técnica - Center ROG Ally (KDE Plasma 6)

Documentación de referencia de archivos, rutas del kernel y funciones del proyecto `org.ally.center` para futuras ampliaciones.

---

## 1. Estructura de archivos del proyecto

* `install.sh`: Instalador automático (`kpackagetool6`, iconos `hicolor`, `sudoers` y `systemd`).
* `uninstall.sh`: Desinstalador completo del widget, iconos, permisos y servicio de arranque.
* `README.md`: Guía de uso e instalación rápida.
* `ARQUITECTURA.md`: Esta guía técnica de referencia.
* `org.ally.center/`: Paquete del widget (Plasmoide KDE Plasma 6)
  * `metadata.json`: Metadatos del applet (`ID: org.ally.center`, `Icon: ally-center`).
  * `contents/config/main.xml`: Esquema KConfig para persistencia de ajustes en Plasma.
  * `contents/icons/`: Iconos SVG (`logo.svg`, `fan.svg`, `leaf.svg`, `balance.svg`, `rocket.svg`, `manual.svg`).
  * `contents/scripts/estado.sh`: Lector rápido de telemetría en POSIX shell (sin `sudo`, ejecutado cada `500 ms` con el popup abierto para cero latencia).
  * `contents/scripts/ally_center.py`: Backend Python con privilegios root (vía `sudoers`) para escritura en hardware y persistencia en el arranque.
  * `contents/ui/main.qml`: Interfaz gráfica QML / Kirigami / PlasmaComponents.

---

## 2. Rutas del kernel de Linux utilizadas (`estado.sh` / `ally_center.py`)

* **Modelo de consola:** `/sys/devices/virtual/dmi/id/product_name` (o `/sys/class/dmi/id/product_name`)
* **Estado del cargador (AC vs Batería):** `/sys/class/power_supply/*/type` (`Mains`) y `online` (`1` o `0`)
* **Perfil de energía ACPI:** `/sys/firmware/acpi/platform_profile` (`low-power`, `balanced`, `performance`)
* **Límites de TDP (`asus-armoury`):** `/sys/class/firmware-attributes/asus-armoury/attributes/{ppt_pl1_spl,ppt_pl2_sppt,ppt_pl3_fppt}/current_value`
  * Ahorro: `13 / 17 / 20 W`
  * Equilibrado: `17 / 20 / 25 W`
  * Rendimiento: `25 / 30 / 35 W` (Batería) | `30 / 35 / 45 W` (AC conectado)
  * Manual: `7–25 W` (Batería) | `7–30 W` (AC conectado)
* **CPU Boost:** `/sys/devices/system/cpu/cpufreq/boost` (`1` = activo, `0` = apagado)
* **Límite de carga de batería:** `/sys/class/power_supply/BAT0/charge_control_end_threshold` (`80` o `100`)
* **Sensores (`hwmon`):**
  * Temperatura APU: `amdgpu` (`temp1_input` / `1000`, sensor instantáneo *edge*) con respaldo automático en `k10temp` (`temp1_input` / `1000`)
  * Consumo APU: `amdgpu` (`power1_input` instantáneo o `power1_average` / `1000000`)
  * RPM Ventiladores: `asus` (`fan1_input`, `fan2_input` vinculados mediante `fan{1,2}_label`)
  * Control de curva PWM: `asus_custom_fan_curve` (`pwm1_enable`, `pwm1_auto_point{1..8}_{temp,pwm}`, `pwm2_auto_point{1..8}_{temp,pwm}`)
* **Persistencia de arranque (`systemd`):** `/etc/ally-center.json` restaurado por `/etc/systemd/system/ally-center.service` al ejecutar `ally_center.py boot`.

---

## 3. Comandos y scripts internos

### Telemetría en tiempo real (`estado.sh`)

| Script | Privilegios | Descripción |
| :--- | :--- | :--- |
| `sh estado.sh` | Usuario (sin `sudo`) | Lee directamente `/sys/` en `< 2 ms` y devuelve un JSON con modelo, RPM, temperatura instantánea de APU, consumo en Watts, estado AC, perfil, TDP, Boost y límite de batería. |

### Control de hardware (`ally_center.py`)

| Comando | Parámetros | Descripción |
| :--- | :--- | :--- |
| `estado` | *(ninguno)* | Comando heredado en Python que devuelve el mismo JSON de telemetría (sin `sudo`). |
| `perfil` | `0`, `1` o `2` | Aplica perfil ACPI (`low-power`, `balanced`, `performance`) y Watts oficiales según AC/Batería. |
| `tdp` | `7`..`30` | Fija `SPL`, `SPPT` y `FPPT` al valor indicado (tope `25W` en batería, `30W` en AC). |
| `boost` | `0` o `1` | Activa o desactiva CPU Boost. |
| `bateria` | `0` o `1` | Fija límite de carga al `80%` (`1`) o `100%` (`0`). |
| `auto` | *(ninguno)* | Devuelve el control de ventiladores a la BIOS (`pwm1_enable = 2`). |
| `ambos` | `0`..`100` `[guardar]` | Fija ambos ventiladores al `%` indicado (`guardar` persiste modo manual en `/etc/ally-center.json`). |
| `cpu_fan` / `gpu_fan` | `0`..`100` | Ajusta individualmente CPU (`pwm1`) o GPU (`pwm2`). |
| `guardar_curva` | `v1,v2,...,v8` | Guarda los 8 puntos en `/etc/ally-center.json` y los aplica al firmware. |
| `boot` | *(ninguno)* | Ejecutado por `systemd` al arrancar para restaurar `/etc/ally-center.json`. |


