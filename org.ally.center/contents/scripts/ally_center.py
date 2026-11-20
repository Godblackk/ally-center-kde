#!/usr/bin/env python3
import glob
import json
import os
import sys
import glob, json, os, subprocess, sys

def buscar_hwmon(nombre_objetivo):
    for archivo_name in glob.glob("/sys/class/hwmon/hwmon*/name"):
        try:
            with open(archivo_name, "r") as f:
                if f.read().strip() == nombre_objetivo:
                    return os.path.dirname(archivo_name)
        except Exception:
            pass
    return None

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

def leer_estado():
    datos = {
        "modelo": detectar_modelo(),
        "cpu_rpm": 0,
        "gpu_rpm": 0,
        "temp": 0,
        "watts": "0.0"

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

    carpeta_temp = buscar_hwmon("k10temp")
    if carpeta_temp:
        try:
            with open(os.path.join(carpeta_temp, "temp1_input"), "r") as f:
                datos["temp"] = int(int(f.read().strip()) / 1000)
        except Exception:
            pass

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

    try:
        with open("/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl1_spl/current_value", "r") as f:
            w_actual = int(f.read().strip())
            datos["tdp"] = max(7, min(30, w_actual))
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
        ruta_enable = os.path.join(carpeta, f"{canal}_enable")
        if os.path.exists(ruta_enable):
            with open(ruta_enable, "w") as f:
                f.write("1")

def ajustar_tdp(watts):
    w = max(7, min(30, int(watts)))
    base = "/sys/class/firmware-attributes/asus-armoury/attributes"
    for attr in ("ppt_pl1_spl", "ppt_pl2_sppt", "ppt_pl3_fppt"):
        ruta = os.path.join(base, attr, "current_value")
        if os.path.exists(ruta):
            try:
                with open(ruta, "w") as f:
                    f.write(str(w))
            except Exception:
                pass

def ajustar_boost(activo):
    ruta = "/sys/devices/system/cpu/cpufreq/boost"
    if os.path.exists(ruta):
        try:
            with open(ruta, "w") as f:
                f.write("1" if activo == "1" else "0")
        except Exception:
            pass

def ajustar_bateria(limite_80):
    ruta = "/sys/class/power_supply/BAT0/charge_control_end_threshold"
    if os.path.exists(ruta):
        try:
            with open(ruta, "w") as f:
                f.write("80" if limite_80 == "1" else "100")
        except Exception:
            pass


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

def ajustar_tdp(watts):
    w = max(7, min(30, int(watts)))
    ruta_perfil = "/sys/firmware/acpi/platform_profile"
    if os.path.exists(ruta_perfil):
        try:
            with open(ruta_perfil, "w") as f:
                f.write("custom")
        except Exception:
            pass
    base = "/sys/class/firmware-attributes/asus-armoury/attributes"
    for attr in ("ppt_pl1_spl", "ppt_pl2_sppt", "ppt_pl3_fppt"):
        ruta = os.path.join(base, attr, "current_value")
        if os.path.exists(ruta):
            try:
                with open(ruta, "w") as f:
                    f.write(str(w))
            except Exception:
                pass

def ajustar_boost(activo):
    ruta = "/sys/devices/system/cpu/cpufreq/boost"
    if os.path.exists(ruta):
        try:
            with open(ruta, "w") as f:
                f.write("1" if activo == "1" else "0")
        except Exception:
            pass

def ajustar_bateria(limite_80):
    ruta = "/sys/class/power_supply/BAT0/charge_control_end_threshold"
    if os.path.exists(ruta):
        try:
            with open(ruta, "w") as f:
                f.write("80" if limite_80 == "1" else "100")
        except Exception:
            pass

def ajustar_perfil(indice):
    idx = int(indice) if 0 <= int(indice) <= 2 else 1
    nombres = ("low-power", "balanced", "performance")
    # Valores oficiales ASUS ROG Ally / Ally X: (SPL, SPPT, FPPT)
    limites_asus = (
        (13, 17, 20),  # 0: Ahorro (Silent)
        (17, 20, 25),  # 1: Equilibrado (Performance)
        (25, 30, 35)   # 2: Rendimiento (Turbo)
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



if __name__ == "__main__":
    args = list(sys.argv)
    args.pop(0)
    if not args:
        sys.exit(1)

    comando = args.pop(0)

    if comando == "estado":
        leer_estado()
        sys.exit(0)
    elif comando == "perfil" and args:
        ajustar_perfil(args.pop(0))
        sys.exit(0)
    elif comando == "tdp" and args:
        ajustar_tdp(args.pop(0))
        sys.exit(0)
    elif comando == "boost" and args:
        ajustar_boost(args.pop(0))
        sys.exit(0)
    elif comando == "bateria" and args:
        ajustar_bateria(args.pop(0))
        sys.exit(0)

    carpeta_curva = buscar_hwmon("asus_custom_fan_curve")
    if not carpeta_curva:
        sys.exit(1)

    if comando == "auto":
        cambiar_modo(carpeta_curva, "auto")
    elif comando in ("ambos", "cpu_fan", "gpu_fan") and args:
        pct = int(args.pop(0))
        canales = ("pwm1", "pwm2") if comando == "ambos" else (("pwm1",) if comando == "cpu_fan" else ("pwm2",))
        aplicar_puntos(carpeta_curva, canales, list(pct for _ in range(8)))
    elif comando == "curva" and args:
        puntos = list(int(x) for x in args.pop(0).split(","))
        if len(puntos) == 8:
            aplicar_puntos(carpeta_curva, ("pwm1", "pwm2"), puntos)

