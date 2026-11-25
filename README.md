<div align="center">
  <img src="docs/capturas/logo-ally.png" alt="Center ROG Ally X Logo" width="96" height="96">
  <h1>⚡ Center ROG Ally / Ally X</h1>
  <p><strong>Centro de control nativo de TDP, curvas de ventilación e iluminación RGB Aura para ASUS ROG Ally y ROG Ally X en Linux (KDE Plasma 6 + Steam Modo Juego).</strong></p>
</div>

---

Inspirado en la comodidad de *Armoury Crate* y *Command Center*, este plasmoid permite gestionar en tiempo real el rendimiento, la refrigeración, el límite de carga de batería y la iluminación RGB directamente desde la bandeja del sistema en el escritorio **y de forma nativa dentro del menú rápido (QAM) de Steam en Modo Juego / Big Picture**, sin depender de Decky Loader.

---

## ✨ Características Principales

* **🚀 Control Total de TDP y Rendimiento:**
  * Perfiles de energía nativos del kernel: **Silencioso**, **Equilibrado** y **Rendimiento**.
  * **Límite TDP Manual (SPL):** Ajuste fino de **7W a 30W** con botones de acceso rápido (`13W`, `17W`, `25W`, `30W`).
  * **Impulso Dinámico (SPPT / FPPT):** Alterna entre vatios sostenidos constantes o picos temporales de impulso (`35W` / `43W`).
  * **CPU Boost:** Activa o desactiva el modo turbo del procesador con un clic.
  * **Cuidado de Batería:** Limita la carga máxima al **80%** o **100%** directamente en el firmware de ASUS para prolongar la vida útil de la batería.
* **🔄 Sincronización Inteligente de Modos (`Sync ON` vs `Por Modo`):**
  * **Modo Sincronizado (`Sync ON`):** Mantiene una configuración única en espejo entre el Escritorio de KDE Plasma y el Modo Juego.
  * **Perfiles Independientes (`Por Modo`):** Guarda y aplica automáticamente configuraciones separadas (TDP, ventiladores, CPU Boost, batería y RGB) para **Escritorio** y **Modo Juego**.
  * **Protección Activa contra el Sistema (`Anti-Override`):** Detecta cambios de sesión (`Gamescope ↔ KDE Plasma`), arranque de `plasma-powerdevil` y conexiones/desconexiones de corriente (`AC ↔ Batería`), restaurando en < 1.5s el perfil del usuario para evitar que el sistema imponga valores predeterminados.
* **❄️ Curvas de Ventilación Independientes (CPU y GPU):**
  * Control granular de **8 puntos de temperatura** (`30°C` a `100°C`) independientes para cada ventilador.
  * Presets integrados: **Silencioso**, **Equilibrado** y **Turbo**, además de la restauración al modo **Automático** de fábrica.
  * **Mecanismo Anti-Bucle:** Bloqueo inteligente durante el desplazamiento manual de puntos para evitar saltos o rebote de valores.
* **🌈 Control Avanzado de Iluminación RGB:**
  * Selector visual de color con previsualización en tiempo real, brillo ajustable (`0%–100%`) y velocidades (`Lento`, `Medio`, `Rápido`).
  * Efectos nativos por hardware: **Fijo**, **Respiración**, **Arcoíris** y **Estrobo**.
  * **Modos Inteligentes por Software:**
    * *Por Temperatura:* Cambia dinámicamente de verde a rojo según la temperatura del APU.
    * *Por Batería:* Refleja el nivel de carga restante mediante colores.
    * *Por Hora del Día:* Adapta la iluminación automáticamente según la franja horaria (mañana, tarde, noche y madrugada).
* **📊 Telemetría en Tiempo Real:**
  * Lectura directa desde sensores `hwmon` del kernel: velocidad en **RPM** de ambos ventiladores, temperatura del **APU**, consumo energético instantáneo en **Vatios (W)**, porcentaje de **batería** y estado de carga (`AC`).
* **🕹️ Integración Nativa en Modo Juego (Sin Decky Loader):**
  * Se inyecta automáticamente en el menú de acceso rápido (`QuickAccess`) de SteamOS / Big Picture mediante WebSocket CEF, sincronizando controles y estado en tiempo real con el widget de escritorio.

---

## 🏗️ Arquitectura del Proyecto

El sistema funciona de manera desacoplada en cuatro capas para garantizar velocidad y seguridad:

1. **Backend Privilegiado (`ally_center.py`):** Script en Python que interactúa directamente con `/sys/class/firmware-attributes/asus-armoury/` y `/sys/class/leds/ally:rgb:joystick_rings/`. Gestiona la persistencia en `/etc/ally-center.json` y se ejecuta sin contraseña mediante una regla de `sudoers`.
2. **Monitor de Sensores (`estado.sh`):** Script ultrarrápido en Bash que lee temperaturas, RPM, consumo eléctrico y estado actual del hardware para alimentar la interfaz sin generar sobrecarga de CPU.
3. **Interfaz Gráfica Escritorio (`main.qml`):** Plasmoid nativo de KDE Plasma 6 construido en QML que reacciona en tiempo real y envía órdenes asíncronas.
4. **Puente Modo Juego y Vigilante (`ally_steam_bridge.py`):** Demonio en segundo plano (`systemd --user`, ordenado tras `plasma-powerdevil.service`) que se conecta por WebSocket al puerto de depuración CEF de Steam (`127.0.0.1:8080`), inyecta el panel en el menú rápido, detecta transiciones `Gamescope ↔ Plasma` y protege el TDP ante cambios externos de energía.
---

## 📋 Requisitos del Sistema

* **Dispositivo:** ASUS ROG Ally X (con módulo del kernel `asus-armoury` cargado).
* **Entorno:** KDE Plasma 6 (Wayland o X11).
* **Dependencias:** `python3`, `python-websockets` (o `python3-websockets`), `bash`, `sudo`, `systemd`.

---

## 🚀 Instalación

1. Clona este repositorio en tu dispositivo:
   ```bash
   git clone https://github.com/Godblackk/ally-center-kde
   cd ally-center-kde
   ```

2. Ejecuta el instalador automático (te pedirá tu contraseña de administrador una única vez para configurar permisos y servicios):
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **Activa el widget en KDE Plasma:**
   * Haz clic derecho en tu barra de tareas / panel → **Añadir elementos gráficos...**
   * Busca **"Center ROG Ally X"** y añádelo a tu panel o bandeja del sistema.

---

## 🗑️ Desinstalación

Si deseas eliminar el plasmoid, los servicios en segundo plano, las reglas de `sudoers` y los archivos de configuración:

```bash
chmod +x uninstall.sh
./uninstall.sh
```

