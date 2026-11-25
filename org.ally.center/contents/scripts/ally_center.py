#!/usr/bin/env python3
import glob
import json
import os
import sys
import glob
import json
import os
import subprocess
import sys
import time
import fcntl

def buscar_hwmon(nombre_objetivo):
    for archivo_name in glob.glob("/sys/class/hwmon/hwmon*/name"):
        try:
            with open(archivo_name, "r") as f:
                if f.read().strip() == nombre_objetivo:
                    return os.path.dirname(archivo_name)
        except Exception:
            pass
    return None


def leer_temp_apu():
    for sensor in ("amdgpu", "k10temp"):
        carpeta = buscar_hwmon(sensor)
        if carpeta:
            try:
                with open(os.path.join(carpeta, "temp1_input"), "r") as f:
                    val = int(int(f.read().strip()) / 1000)
                    if val > 0:
                        return val
            except Exception:
                pass
    return 0


def leer_estado():
    datos = {
        "modelo": detectar_modelo(),
        "cpu_rpm": 0,
        "gpu_rpm": 0,
        "temp": 0,
        "watts": "0.0",
        "ac_conectado": cargador_conectado()

    }
    carpeta_asus = buscar_hwmon("asus")
    if carpeta_asus:
        for num in ("1", "2"):
            try:
                with open(os.path.join(carpeta_asus, f"fan{num}_label"), "r") as f:
                    label = f.read().strip()
                with open(os.path.join(carpeta_asus, f"fan{num}_input"), "r") as f:
                    rpm = int(f.read().strip())
                if label == "cpu_fan":
                    datos["cpu_rpm"] = rpm
                elif label == "gpu_fan":
                    datos["gpu_rpm"] = rpm
            except Exception:
                pass

    datos["temp"] = leer_temp_apu()

    carpeta_gpu = buscar_hwmon("amdgpu")
    if carpeta_gpu:
        try:
            with open(os.path.join(carpeta_gpu, "power1_average"), "r") as f:
                uw = int(f.read().strip())
                datos["watts"] = f"{uw / 1000000.0:.1f}"
        except Exception:
            pass

    try:
        with open("/sys/firmware/acpi/platform_profile", "r") as f:
            perfil_str = f.read().strip()
        mapa_perfiles = {"low-power": 0, "quiet": 0, "balanced": 1, "performance": 2}
        if perfil_str in mapa_perfiles:
            datos["perfil"] = mapa_perfiles[perfil_str]
    except Exception:
        pass

    datos["ac_conectado"] = cargador_conectado()
    try:
        with open("/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl1_spl/current_value", "r") as f:
            w_actual = int(f.read().strip())
            max_w = 30 if datos["ac_conectado"] else 25
            datos["tdp"] = max(7, min(max_w, w_actual))
    except Exception:
        pass

    try:
        with open("/sys/devices/system/cpu/cpufreq/boost", "r") as f:
            datos["boost"] = (f.read().strip() == "1")
    except Exception:
        pass

    try:
        with open("/sys/class/power_supply/BAT0/charge_control_end_threshold", "r") as f:
            datos["bateria_80"] = (int(f.read().strip()) <= 85)
    except Exception:
        pass


    if os.path.exists(CONFIG_SISTEMA):
        try:
            cfg = cargar_estado_sistema()
            sync = cfg.get("sync_modos", True)
            datos["sync_modos"] = sync
            fuente = cfg if sync else cfg["perfiles_modo"]["desktop"]
            for k in ("curva", "modo_fan", "tdp_manual", "tdp", "tdp_boost", "perfil", "boost", "bateria_80", "rgb_modo", "rgb", "rgb_brillo", "rgb_vel", "fan_pct", "vincular_fans", "cpu_pct", "gpu_pct"):
                if k in fuente:
                    datos[k] = fuente[k]
        except Exception:
            pass




    print(json.dumps(datos))

def cambiar_modo(carpeta, modo):
    valor = "1" if modo == "manual" else "2"
    for pwm in ("pwm1_enable", "pwm2_enable"):
        ruta = os.path.join(carpeta, pwm)
        if os.path.exists(ruta):
            with open(ruta, "w") as f:
                f.write(valor)

def aplicar_puntos(carpeta, canales, lista_porcentajes):
    temps_validas = range(30, 105, 10)
    for canal in canales:
        ruta_enable = os.path.join(carpeta, f"{canal}_enable")
        if os.path.exists(ruta_enable):
            with open(ruta_enable, "w") as f:
                f.write("1")
        for idx, temp in enumerate(temps_validas, start=1):
            ruta_temp = os.path.join(carpeta, f"{canal}_auto_point{idx}_temp")
            if os.path.exists(ruta_temp):
                with open(ruta_temp, "w") as f:
                    f.write(str(temp))
        for idx, pct in enumerate(lista_porcentajes, start=1):
            valor_pwm = str(int(max(0, min(100, int(pct))) * 2.55))
            ruta_punto = os.path.join(carpeta, f"{canal}_auto_point{idx}_pwm")
            if os.path.exists(ruta_punto):
                with open(ruta_punto, "w") as f:
                    f.write(valor_pwm)
        if os.path.exists(ruta_enable):
            with open(ruta_enable, "w") as f:
                f.write("1")



def detectar_modelo():
    try:
        with open("/sys/devices/virtual/dmi/id/product_name", "r") as f:
            prod = f.read().strip()
        if "Ally X" in prod or "RC72" in prod:
            return "Center ROG Ally X"
        elif "Ally" in prod or "RC71" in prod:
            return "Center ROG Ally"
    except Exception:
        pass
    return "Center ROG Ally X"

def ajustar_tdp(watts, boost_pico=None):
    max_w = 30 if cargador_conectado() else 25
    w = max(7, min(max_w, int(watts)))
    if boost_pico is None and os.path.exists(CONFIG_SISTEMA):
        try:
            with open(CONFIG_SISTEMA, "r") as f:
                boost_pico = bool(json.load(f).get("tdp_boost", False))
        except Exception:
            boost_pico = False
    usar_pico = bool(boost_pico) and (w >= 25)
    base = "/sys/class/firmware-attributes/asus-armoury/attributes"
    for attr in ("ppt_pl1_spl", "ppt_pl2_sppt", "ppt_pl3_fppt"):
        dir_attr = os.path.join(base, attr)
        ruta = os.path.join(dir_attr, "current_value")
        if os.path.exists(ruta):
            try:
                with open(os.path.join(dir_attr, "min_value"), "r") as fm:
                    min_hw = int(fm.read().strip())
                with open(os.path.join(dir_attr, "max_value"), "r") as fx:
                    max_hw = int(fx.read().strip())
                if attr != "ppt_pl1_spl" and usar_pico:
                    val_escribir = max_hw
                else:
                    val_escribir = max(min_hw, min(max_hw, w))
                with open(ruta, "w") as f:
                    f.write(str(val_escribir))
            except Exception:
                pass
    guardar_estado_sistema("tdp", w)
    guardar_estado_sistema("tdp_manual", True)
    guardar_estado_sistema("tdp_boost", usar_pico)



def ajustar_boost(activo):
    ruta = "/sys/devices/system/cpu/cpufreq/boost"
    if os.path.exists(ruta):
        try:
            with open(ruta, "w") as f:
                f.write("1" if activo == "1" else "0")
        except Exception:
            pass

    guardar_estado_sistema("boost", activo == "1")

def ajustar_bateria(limite_80):
    ruta = "/sys/class/power_supply/BAT0/charge_control_end_threshold"
    if os.path.exists(ruta):
        try:
            with open(ruta, "w") as f:
                f.write("80" if limite_80 == "1" else "100")
        except Exception:
            pass
    guardar_estado_sistema("bateria_80", limite_80 == "1")


def cargador_conectado():
    for fuente in glob.glob("/sys/class/power_supply/*"):
        try:
            with open(os.path.join(fuente, "type"), "r") as f:
                if f.read().strip() == "Mains":
                    with open(os.path.join(fuente, "online"), "r") as fo:
                        return fo.read().strip() == "1"
        except Exception:
            pass
    return False



def ajustar_perfil(indice):
    idx = int(indice) if 0 <= int(indice) <= 2 else 1
    nombres = ("low-power", "balanced", "performance")
    en_ac = cargador_conectado()
    # Valores oficiales ASUS ROG Ally / Ally X: (SPL, SPPT, FPPT)
    limites_asus = (
        (13, 17, 20),                                 # 0: Ahorro (Silent)
        (17, 20, 25),                                 # 1: Equilibrado (Performance)
        (30, 35, 45) if en_ac else (25, 30, 35)       # 2: Rendimiento (Turbo 30W AC / 25W Bat)
    )

    ruta = "/sys/firmware/acpi/platform_profile"
    if os.path.exists(ruta):
        try:
            with open(ruta, "w") as f:
                f.write(nombres[idx])
        except Exception:
            pass

    spl, sppt, fppt = limites_asus[idx]
    base = "/sys/class/firmware-attributes/asus-armoury/attributes"
    for attr, val in (("ppt_pl1_spl", spl), ("ppt_pl2_sppt", sppt), ("ppt_pl3_fppt", fppt)):
        ruta_w = os.path.join(base, attr, "current_value")
        if os.path.exists(ruta_w):
            try:
                with open(ruta_w, "w") as f:
                    f.write(str(val))
            except Exception:
                pass
    guardar_estado_sistema("perfil", idx)
    guardar_estado_sistema("tdp_manual", False)


CONFIG_SISTEMA = "/etc/ally-center.json"
MODO_ACTUAL = "desktop"
CLAVES_PERFIL = (
    "curva", "tdp_manual", "tdp", "tdp_boost", "perfil", "boost",
    "bateria_80", "rgb_modo", "rgb", "rgb_brillo", "rgb_vel",
    "modo_fan", "fan_pct", "vincular_fans", "cpu_pct", "gpu_pct"
)


def cargar_estado_sistema():
    estado = {}
    if os.path.exists(CONFIG_SISTEMA):
        try:
            with open(CONFIG_SISTEMA, "r") as f:
                estado = json.load(f)
        except Exception:
            estado = {}
    estado.setdefault("sync_modos", True)
    if not isinstance(estado.get("perfiles_modo"), dict):
        base = {k: estado[k] for k in CLAVES_PERFIL if k in estado}
        estado["perfiles_modo"] = {"desktop": dict(base), "game": dict(base)}
    for m in ("desktop", "game"):
        if not isinstance(estado["perfiles_modo"].get(m), dict):
            estado["perfiles_modo"][m] = {k: estado[k] for k in CLAVES_PERFIL if k in estado}
    return estado


def guardar_estado_sistema(clave, valor):
    estado = cargar_estado_sistema()
    perfiles = estado["perfiles_modo"]
    if estado.get("sync_modos", True):
        estado[clave] = valor
        if clave in CLAVES_PERFIL:
            perfiles["desktop"][clave] = valor
            perfiles["game"][clave] = valor
    else:
        t = "game" if MODO_ACTUAL == "game" else "desktop"
        if clave in CLAVES_PERFIL:
            perfiles[t][clave] = valor
        else:
            estado[clave] = valor

    try:
        with open(CONFIG_SISTEMA, "w") as f:
            json.dump(estado, f, indent=2)
    except Exception:
        pass



LED_RGB_DIR = "/sys/class/leds/ally:rgb:joystick_rings"


MODOS_HW_AURA = {
    "fijo": 0x00,
    "temp": 0x00,
    "bateria": 0x00,
    "hora": 0x00,
    "respiracion": 0x01,
    "ciclo": 0x02,
    "arcoiris": 0x03,
    "pulso": 0x04,
}

VELOCIDADES_AURA = {
    1: 0xE1,  # Lenta
    2: 0xEB,  # Media
    3: 0xF5,  # Rápida
}


def calibrar_color_mcu(r, g, b):
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    # Compensa la mayor luminancia de los LEDs verde y azul en el difusor de la ROG Ally
    g_cal = int(round(255.0 * ((g / 255.0) ** 1.35)))
    b_cal = int(round(255.0 * ((b / 255.0) ** 1.45)))
    if r > 180 and g < 60 and b < 60:
        g_cal = int(g_cal * 0.4)
        b_cal = 0
    return r, g_cal, b_cal


def escribir_led_rgb(r, g, b, brillo_pct, guardar_mcu=True, modo_hw=0x00, vel=2):
    pct = max(0, min(100, int(brillo_pct)))
    factor = pct / 100.0
    r_c, g_c, b_c = calibrar_color_mcu(r, g, b)
    r_out = int(round(r_c * factor))
    g_out = int(round(g_c * factor))
    b_out = int(round(b_c * factor))
    modo_efectivo = 0x00 if pct == 0 else modo_hw
    vel_byte = VELOCIDADES_AURA.get(int(vel), 0xEB)
    pkt_color = bytearray(64)
    pkt_color[:12] = bytes([0x5A, 0xB3, 0x00, modo_efectivo, r_out, g_out, b_out, vel_byte, 0x00, 0x00, 0x00, 0x00])
    pkt_apply = bytearray(64)
    pkt_apply[:2] = bytes([0x5A, 0xB5])

    for h in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(h, "device/uevent"), "r") as f:
                uev = f.read()
            if "0003:00000B05:00001B4C" in uev or "0003:00000B05:00001ABE" in uev:
                dev = "/dev/" + os.path.basename(h)
                fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
                os.write(fd, pkt_color)
                os.write(fd, pkt_apply)
                os.close(fd)
        except Exception:
            pass




def ajustar_rgb(modo, r, g, b, brillo_pct, activo=True, vel=2):
    modo_valido = modo if modo in MODOS_HW_AURA else "fijo"
    rgb_list = [max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))]
    brillo = max(0, min(100, int(brillo_pct)))
    vel_int = max(1, min(3, int(vel)))
    activo_bool = bool(int(activo)) if str(activo).isdigit() else (str(activo).lower() not in ("false", "0", "off"))
    guardar_estado_sistema("rgb_modo", modo_valido)
    guardar_estado_sistema("rgb", rgb_list)
    guardar_estado_sistema("rgb_brillo", brillo)
    guardar_estado_sistema("rgb_activo", activo_bool)
    guardar_estado_sistema("rgb_vel", vel_int)
    if os.path.exists("/tmp/ally_rgb_cache"):
        os.remove("/tmp/ally_rgb_cache")
    if os.path.exists("/tmp/ally_temp_tramo"):
        os.remove("/tmp/ally_temp_tramo")
    rc, gc, bc = calcular_color_dinamico(modo_valido, *rgb_list)
    escribir_led_rgb(rc, gc, bc, brillo if activo_bool else 0, modo_hw=MODOS_HW_AURA[modo_valido], vel=vel_int)




def calcular_color_dinamico(modo, r_base=0, g_base=210, b_base=255):
    if modo == "temp":
        temp = leer_temp_apu() or 50
        tramo_file = "/tmp/ally_temp_tramo"
        prev_tramo = -1
        if os.path.exists(tramo_file):
            try:
                prev_tramo = int(open(tramo_file).read().strip())
            except Exception:
                pass

        # Histéresis de 2 °C al bajar para evitar parpadeo en fronteras (65/66, 75/76, 85/86)
        if temp > 85 or (prev_tramo == 4 and temp > 83):
            tramo = 4   # Rojo (> 85 °C)
        elif temp > 75 or (prev_tramo == 3 and temp > 73):
            tramo = 3   # Naranja (76 - 85 °C)
        elif temp > 65 or (prev_tramo == 2 and temp > 63):
            tramo = 2   # Amarillo (66 - 75 °C)
        elif temp > 35 or (prev_tramo == 1 and temp > 33):
            tramo = 1   # Verde (36 - 65 °C)
        else:
            tramo = 0   # Cian / Azul (<= 35 °C)

        try:
            with open(tramo_file, "w") as tf:
                tf.write(str(tramo))
        except Exception:
            pass

        colores_temp = (
            (0, 210, 255),  # 0: Cian / Azul
            (0, 255, 0),    # 1: Verde
            (255, 165, 0),  # 2: Amarillo
            (255, 110, 0),  # 3: Naranja
            (255, 0, 0),    # 4: Rojo
        )
        return colores_temp[tramo]
         # Rojo (> 85 °C)


    elif modo == "bateria":
        if cargador_conectado():
            return (0, 255, 0)        # Verde si el cargador está conectado
        cap = 80
        for bat_name in ("BAT0", "BATT"):
            bat_path = f"/sys/class/power_supply/{bat_name}/capacity"
            if os.path.exists(bat_path):
                try:
                    with open(bat_path, "r") as f:
                        cap = int(f.read().strip())
                    break
                except Exception:
                    pass
        if cap > 60:
            return (0, 255, 0)        # Verde (> 60%)
        elif cap >= 25:
            return (255, 165, 0)      # Amarillo dorado (25% - 60%)
        elif cap > 10:
            return (255, 110, 0)      # Naranja (11% - 24%)
        return (255, 0, 0)            # Rojo crítica (<= 10%)

    elif modo == "hora":
        h = time.localtime().tm_hour
        if 7 <= h < 13:
            return (255, 255, 255)    # Mañana: blanco puro calibrado
        elif 13 <= h < 20:
            return (0, 210, 255)      # Tarde: cian vibrante calibrado
        return (255, 0, 0)            # Noche: rojo calibrado anti-deslumbramiento

    return (int(r_base), int(g_base), int(b_base))



def restaurar_boot():
    if not os.path.exists(CONFIG_SISTEMA):
        return
    try:
        with open(CONFIG_SISTEMA, "r") as f:
            estado = json.load(f)
    except Exception:
        return

    if estado.get("tdp_manual") and "tdp" in estado:
        ajustar_tdp(estado["tdp"], estado.get("tdp_boost", False))
        time.sleep(0.5)
    else:
        if "perfil" in estado:
            ajustar_perfil(estado["perfil"])
        time.sleep(0.5)


    if "boost" in estado:
        ajustar_boost("1" if estado["boost"] else "0")
    if "bateria_80" in estado:
        ajustar_bateria("1" if estado["bateria_80"] else "0")

    carpeta_curva = buscar_hwmon("asus_custom_fan_curve")
    if carpeta_curva:
        modo_fan = estado.get("modo_fan", "auto")
        if modo_fan == "auto":
            cambiar_modo(carpeta_curva, "auto")
        elif modo_fan == "manual" and "fan_pct" in estado:
            pct = int(estado["fan_pct"])
            aplicar_puntos(carpeta_curva, ("pwm1", "pwm2"), [pct] * 8)
        elif modo_fan == "curva" and "curva" in estado:
            puntos = estado["curva"]
            if len(puntos) == 8:
                aplicar_puntos(carpeta_curva, ("pwm1", "pwm2"), puntos)


    if "rgb_modo" in estado or "rgb" in estado:
        modo_rgb = estado.get("rgb_modo", "fijo")
        rgb_vals = estado.get("rgb", [0, 210, 255])
        brillo_rgb = estado.get("rgb_brillo", 80)
        activo_rgb = estado.get("rgb_activo", True)
        vel_rgb = estado.get("rgb_vel", 2)
        rc, gc, bc = calcular_color_dinamico(modo_rgb, *rgb_vals)
        escribir_led_rgb(rc, gc, bc, brillo_rgb if activo_rgb else 0, modo_hw=MODOS_HW_AURA.get(modo_rgb, 0x00), vel=vel_rgb)


if __name__ == "__main__":
    args = list(sys.argv)
    args.pop(0)
    if "--modo" in args:
        idx = args.index("--modo")
        if idx + 1 < len(args):
            MODO_ACTUAL = "game" if args[idx + 1] == "game" else "desktop"
            del args[idx:idx + 2]
    if not args:
        sys.exit(1)

    comando = args.pop(0)

    if comando != "estado":
        lock_fd = open("/tmp/ally_center.lock", "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

    if comando == "estado":
        leer_estado()
        sys.exit(0)
    elif comando == "sync_modos" and args:
        activo = args.pop(0) == "1"
        est = cargar_estado_sistema()
        est["sync_modos"] = activo
        if activo:
            origen = MODO_ACTUAL
            destino = "desktop" if origen == "game" else "game"
            maestro = dict(est["perfiles_modo"].get(origen, {}))
            if not maestro:
                maestro = {k: est[k] for k in CLAVES_PERFIL if k in est}
            est["perfiles_modo"][origen] = dict(maestro)
            est["perfiles_modo"][destino] = dict(maestro)
            est.update(maestro)
        with open(CONFIG_SISTEMA, "w") as f:
            json.dump(est, f, indent=2)
        if activo:
            restaurar_boot()
        sys.exit(0)
    elif comando == "aplicar_modo" and args:
        objetivo = "game" if args.pop(0) == "game" else "desktop"
        est = cargar_estado_sistema()
        if not est.get("sync_modos", True):
            p = est["perfiles_modo"].get(objetivo, {})
            if p:
                est.update(p)
                with open(CONFIG_SISTEMA, "w") as f:
                    json.dump(est, f, indent=2)
                restaurar_boot()
        sys.exit(0)

    elif comando == "perfil" and args:
        ajustar_perfil(args.pop(0))
        sys.exit(0)
    elif comando == "tdp" and args:
        w_arg = args.pop(0)
        b_arg = (args.pop(0) == "1") if args else None
        ajustar_tdp(w_arg, b_arg)
        sys.exit(0)
    elif comando == "boost" and args:
        ajustar_boost(args.pop(0))
        sys.exit(0)
    elif comando == "bateria" and args:
        ajustar_bateria(args.pop(0))
        sys.exit(0)
    elif comando == "boot":
        restaurar_boot()
        sys.exit(0)
    elif comando == "rgb" and len(args) >= 5:
        activo_arg = args[5] if len(args) >= 6 else True
        vel_arg = args[6] if len(args) >= 7 else 2
        ajustar_rgb(args[0], args[1], args[2], args[3], args[4], activo_arg, vel_arg)
        sys.exit(0)
    elif comando == "rgb_live" and len(args) >= 5:
        m_rgb, r_s, g_s, b_s, br_s, *_ = args
        vel_live = int(args[5]) if len(args) >= 6 else 2
        rc, gc, bc = calcular_color_dinamico(m_rgb, int(r_s), int(g_s), int(b_s))
        escribir_led_rgb(rc, gc, bc, int(br_s), guardar_mcu=False, modo_hw=MODOS_HW_AURA.get(m_rgb, 0x00), vel=vel_live)
        sys.exit(0)
    elif comando == "rgb_tick":
        est = cargar_estado_sistema()
        st = est if est.get("sync_modos", True) else est["perfiles_modo"].get(MODO_ACTUAL, est)
        m = st.get("rgb_modo", "fijo")
        br = st.get("rgb_brillo", 80)
        if m in ("bateria", "temperatura", "hora") and br > 0:
            rgb_base = st.get("rgb", [0, 210, 255])
            rc, gc, bc = calcular_color_dinamico(m, rgb_base)
            cache_file = "/tmp/ally_rgb_tick_cache"
            firma = f"{rc},{gc},{bc},{br}"
            prev = open(cache_file).read().strip() if os.path.exists(cache_file) else ""
            if firma != prev:
                escribir_led_rgb(rc, gc, bc, br, guardar_eca=False)
                with open(cache_file, "w") as cf:
                    cf.write(firma)
        sys.exit(0)

    elif comando == "guardar_curva" and args:
        puntos = [int(x) for x in args.pop(0).split(",")]
        if len(puntos) == 8:
            guardar_estado_sistema("modo_fan", "curva")
            guardar_estado_sistema("curva", puntos)
            carpeta_curva = buscar_hwmon("asus_custom_fan_curve")
            if carpeta_curva:
                aplicar_puntos(carpeta_curva, ("pwm1", "pwm2"), puntos)
        sys.exit(0)

    carpeta_curva = buscar_hwmon("asus_custom_fan_curve")
    if not carpeta_curva:
        sys.exit(1)

    if comando == "auto":
        cambiar_modo(carpeta_curva, "auto")
        guardar_estado_sistema("modo_fan", "auto")
    elif comando in ("ambos", "cpu_fan", "gpu_fan") and args:
        pct = int(args.pop(0))
        canales = ("pwm1", "pwm2") if comando == "ambos" else (("pwm1",) if comando == "cpu_fan" else ("pwm2",))
        aplicar_puntos(carpeta_curva, canales, list(pct for _ in range(8)))
        guardar_estado_sistema("modo_fan", "manual")
        if comando == "ambos":
            guardar_estado_sistema("vincular_fans", True)
            guardar_estado_sistema("fan_pct", pct)
            guardar_estado_sistema("cpu_pct", pct)
            guardar_estado_sistema("gpu_pct", pct)
        elif comando == "cpu_fan":
            guardar_estado_sistema("vincular_fans", False)
            guardar_estado_sistema("cpu_pct", pct)
        elif comando == "gpu_fan":
            guardar_estado_sistema("vincular_fans", False)
            guardar_estado_sistema("gpu_pct", pct)

    elif comando == "curva" and args:
        puntos = list(int(x) for x in args.pop(0).split(","))
        if len(puntos) == 8:
            aplicar_puntos(carpeta_curva, ("pwm1", "pwm2"), puntos)

