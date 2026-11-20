# Center ROG Ally (KDE Plasma 6)

Centro de control nativo de energia, TDP, CPU Boost, limite de carga de bateria y curvas personalizadas de ventiladores para **ASUS ROG Ally** y **ROG Ally X** en Linux (CachyOS / Arch Linux / KDE Plasma 6).

## Caracteristicas incluidas

- **Deteccion automatica de hardware:** Identifica automaticamente el modelo exacto de consola (`ROG Ally` o `ROG Ally X`) y el estado de conexion a corriente (`AC` vs `Bateria`).
- **Telemetria en tiempo real:** Lectura directa desde `hwmon` de RPM de CPU y GPU, temperatura de la APU (`°C`) y consumo energetico en tiempo real (`W`).
- **Perfiles oficiales de ASUS y TDP dinamico (AC / Bateria):**
  - Perfiles **Ahorro (13W)** (`13/17/20W`), **Equilibrado (17W)** (`17/20/25W`) y **Rendimiento** (`25/30/35W` en bateria y `30/35/45W` con cargador conectado).
  - **Limite TDP Manual (`7W`–`25W` en bateria / `7W`–`30W` con cargador):** Ajusta el tope maximo automaticamente al conectar o desconectar el cargador, parte desde los Watts del perfil activo y deshabilita el selector de perfiles mientras esta activo.
  - Sincronizacion en tiempo real de **CPU Boost** y **Cuidado de Bateria (limite al 80%)** con el estado real del kernel.
- **Control avanzado de ventiladores:**
  - Modos **Automatico (BIOS)**, **Manual (Perfiles / Individual / Vinculado)** y **Curva Personalizada de 8 puntos**.
  - **Grafico interactivo con interpolacion continua:** Calcula y aplica el porcentaje exacto entre nodos grado a grado con un indicador visual dinamico de la temperatura actual.
- **Iconos dinamicos en la barra de tareas:** Cambia automaticamente segun el perfil activo (`leaf.svg` para Ahorro, `balance.svg` para Equilibrado, `rocket.svg` para Rendimiento y `manual.svg` para TDP Manual).
- **Persistencia en el arranque y Modo Juego (`systemd`):** Guarda el estado en `/etc/ally-center.json` y restaura automaticamente TDP, perfil, CPU Boost, limite de bateria y curva de hardware al encender la consola mediante `ally-center.service` (compatible con inicio directo en Gamescope / SteamOS).


## Instalación rápida (después de formatear o en un sistema limpio)

1. Abre una terminal en el escritorio KDE Plasma y ejecuta:
   ```bash
   git clone https://github.com/Godblackk/ally-center-kde.git
   cd ally-center-kde
   ./install.sh
   ```
2. Introduce tu contraseña de usuario (`sudo`) cuando el instalador la solicite para configurar los permisos de hardware y el servicio de arranque.
3. Cuando termine y se reinicie la barra de tareas:
   * Haz **clic derecho** en la barra de tareas → **Añadir o gestionar widgets**.
   * Busca **Center ROG Ally** y haz clic en él para anclarlo en tu panel.

---

## ¿Qué configura automáticamente `./install.sh`?

* **Registro del widget:** Instala `org.ally.center` en KDE Plasma 6 mediante `kpackagetool6`.
* **Permisos sin contraseña (`sudoers`):** Crea `/etc/sudoers.d/ally-center` para que el widget pueda ajustar TDP, CPU Boost, límite de batería y ventiladores en tiempo real sin pedir clave.
* **Persistencia al arrancar (`systemd`):** Instala y activa `ally-center.service`, que lee `/etc/ally-center.json` al encender la consola y aplica tu último TDP, perfil, Boost, límite de carga al 80% y curva de ventiladores (compatible con inicio directo en **Modo Juego / Gamescope**).

---

## Actualizar el widget en el futuro

Si realizas mejoras o descargas una actualización desde GitHub:
```bash
cd ~/ally-center-kde
git pull
./install.sh
```
