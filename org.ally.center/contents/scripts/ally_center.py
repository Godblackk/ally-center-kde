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
            with open(CONFIG_SISTEMA, "r") as f:
                cfg = json.load(f)
                if "curva" in cfg:
                    datos["curva"] = cfg["curva"]
                if "modo_fan" in cfg:
                    datos["modo_fan"] = cfg["modo_fan"]
                if "tdp_manual" in cfg:
                    datos["tdp_manual"] = cfg["tdp_manual"]
                if "tdp_boost" in cfg:
                    datos["tdp_boost"] = cfg["tdp_boost"]
                if "boost" in cfg:
                    datos["boost"] = cfg["boost"]
                if "bateria_80" in cfg:
                    datos["bateria_80"] = cfg["bateria_80"]
                if "rgb_modo" in cfg:
                    datos["rgb_modo"] = cfg["rgb_modo"]
                if "rgb" in cfg:
                    datos["rgb"] = cfg["rgb"]
                if "rgb_brillo" in cfg:
                    datos["rgb_brillo"] = cfg["rgb_brillo"]

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

def guardar_estado_sistema(clave, valor):
    estado = {}
    if os.path.exists(CONFIG_SISTEMA):
        try:
            with open(CONFIG_SISTEMA, "r") as f:
                estado = json.load(f)
        except Exception:
            estado = {}
    estado[clave] = valor
    try:
        with open(CONFIG_SISTEMA, "w") as f:
            json.dump(estado, f, indent=2)
    except Exception:
        pass


LED_RGB_DIR = "/sys/class/leds/ally:rgb:joystick_rings"


def escribir_led_rgb(r, g, b, brillo_pct, guardar_mcu=True):
    pct = max(0, min(100, int(brillo_pct)))
    factor = pct / 100.0
    r_out = int(round(max(0, min(255, int(r))) * factor))
    g_out = int(round(max(0, min(255, int(g))) * factor))
    b_out = int(round(max(0, min(255, int(b))) * factor))

    # Solo toca sysfs si está apagado o si las zonas aún no están habilitadas (evita parpadeo)
    if os.path.exists(LED_RGB_DIR):
        try:
            ruta_mi = os.path.join(LED_RGB_DIR, "multi_intensity")
            objetivo = "255 255 255 255" if pct > 0 else "0 0 0 0"
            with open(ruta_mi, "r") as f:
                actual = f.read().strip()
            if actual != objetivo:
                with open(ruta_mi, "w") as f:
                    f.write(objetivo)
            ruta_br = os.path.join(LED_RGB_DIR, "brightness")
            brillo_obj = "255" if pct > 0 else "0"
            with open(ruta_br, "r") as f:
                br_act = f.read().strip()
            if br_act != brillo_obj:
                with open(ruta_br, "w") as f:
                    f.write(brillo_obj)
        except Exception:
            pass

    pkt_color = bytearray(64)
    pkt_color[:7] = bytes([0x5A, 0xB3, 0x00, 0x00, r_out, g_out, b_out])
    pkt_apply = bytearray(64)
    pkt_apply[:2] = bytes([0x5A, 0xB5])
    pkt_save = bytearray(64)
    pkt_save[:2] = bytes([0x5A, 0xB4])

    for h in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(h, "device/uevent"), "r") as f:
                uev = f.read()
            if "0003:00000B05:00001B4C" in uev or "0003:00000B05:00001ABE" in uev:
                dev = "/dev/" + os.path.basename(h)
                fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
                os.write(fd, pkt_color)
                os.write(fd, pkt_apply)
                if guardar_mcu:
                    os.write(fd, pkt_save)
                os.close(fd)
        except Exception:
            pass




def calcular_color_dinamico(modo, r_base=0, g_base=210, b_base=255):
    if modo == "temp":
        temp = leer_temp_apu() or 55
        if temp < 55:
            return (0, 210, 255)      # Cian frío
        elif temp < 72:
            return (40, 230, 90)      # Verde templado
        elif temp < 84:
            return (255, 110, 0)      # Naranja carga alta
        return (255, 15, 15)          # Rojo alerta térmica

    elif modo == "bateria":
        cap = 80
        try:
            with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
                cap = int(f.read().strip())
        except Exception:
            pass
        if cap > 60:
            return (35, 225, 85)      # Verde batería alta
        elif cap >= 25:
            return (255, 180, 0)      # Ámbar batería media
        return (255, 20, 20)          # Rojo batería baja

    elif modo == "hora":
        h = time.localtime().tm_hour
        if 7 <= h < 13:
            return (255, 235, 195)    # Mañana: blanco cálido
        elif 13 <= h < 20:
            return (0, 210, 255)      # Tarde: cian vibrante
        return (255, 35, 20)          # Noche: rojo tenue anti-deslumbramiento

    return (int(r_base), int(g_base), int(b_base))


def ajustar_rgb(modo, r, g, b, brillo_pct):
    modo_valido = modo if modo in ("fijo", "temp", "bateria", "hora") else "fijo"
    rgb_list = [max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))]
    brillo = max(0, min(100, int(brillo_pct)))
    guardar_estado_sistema("rgb_modo", modo_valido)
    guardar_estado_sistema("rgb", rgb_list)
    guardar_estado_sistema("rgb_brillo", brillo)
    if os.path.exists("/tmp/ally_rgb_cache"):
        os.remove("/tmp/ally_rgb_cache")
    rc, gc, bc = calcular_color_dinamico(modo_valido, *rgb_list)
    escribir_led_rgb(rc, gc, bc, brillo)


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
        rc, gc, bc = calcular_color_dinamico(modo_rgb, *rgb_vals)
        escribir_led_rgb(rc, gc, bc, brillo_rgb)





if __name__ == "__main__":
    args = list(sys.argv)
    args.pop(0)
    if not args:
        sys.exit(1)

    comando = args.pop(0)

    if comando != "estado":
        lock_fd = open("/tmp/ally_center.lock", "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)


    if comando == "estado":
        leer_estado()
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
        ajustar_rgb(args[0], args[1], args[2], args[3], args[4])
        sys.exit(0)
    elif comando == "rgb_live" and len(args) >= 5:
        m_rgb, r_s, g_s, b_s, br_s, *_ = args
        rc, gc, bc = calcular_color_dinamico(m_rgb, r_s, g_s, b_s)
        escribir_led_rgb(rc, gc, bc, br_s, guardar_mcu=False)
        sys.exit(0)
    elif comando == "rgb_tick":
        if os.path.exists(CONFIG_SISTEMA):
            try:
                with open(CONFIG_SISTEMA, "r") as f:
                    st = json.load(f)
                m = st.get("rgb_modo", "fijo")
                br = st.get("rgb_brillo", 80)
                if m in ("temp", "bateria", "hora") and br > 0:
                    rgb_base = st.get("rgb", (0, 210, 255))
                    rc, gc, bc = calcular_color_dinamico(m, *rgb_base)
                    cache_file = "/tmp/ally_rgb_cache"
                    firma = f"{rc},{gc},{bc},{br}"
                    prev = open(cache_file).read().strip() if os.path.exists(cache_file) else ""
                    if firma != prev:
                        escribir_led_rgb(rc, gc, bc, br, guardar_mcu=False)
                        with open(cache_file, "w") as cf:
                            cf.write(firma)
            except Exception:
                pass
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
        guardar = (args and args.pop(0) == "guardar")
        canales = ("pwm1", "pwm2") if comando == "ambos" else (("pwm1",) if comando == "cpu_fan" else ("pwm2",))
        aplicar_puntos(carpeta_curva, canales, list(pct for _ in range(8)))
        if guardar and comando == "ambos":
            guardar_estado_sistema("modo_fan", "manual")
            guardar_estado_sistema("fan_pct", pct)
    elif comando == "curva" and args:
        puntos = list(int(x) for x in args.pop(0).split(","))
        if len(puntos) == 8:
            aplicar_puntos(carpeta_curva, ("pwm1", "pwm2"), puntos)

