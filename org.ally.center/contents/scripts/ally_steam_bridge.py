#!/usr/bin/env python3
import asyncio
import json
import os
import subprocess
import urllib.request
import websockets


SCRIPT_ALLY = os.path.expanduser("~/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py")
SCRIPT_ESTADO = os.path.expanduser("~/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/estado.sh")


def obtener_targets():
    try:
        with urllib.request.urlopen("http://localhost:8080/json", timeout=1.5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []


def ejecutar_ally(args, modo="game"):
    cmd = ["sudo", "/usr/bin/python3", SCRIPT_ALLY, "--modo", modo] + args
    subprocess.run(cmd, capture_output=True, text=True)


def leer_estado_str():
    res_sh = subprocess.run(["/bin/sh", SCRIPT_ESTADO], capture_output=True, text=True)
    datos = json.loads(res_sh.stdout.strip() or "{}")
    try:
        with open("/etc/ally-center.json", "r") as f:
            cfg = json.load(f)
            fuente = cfg if cfg.get("sync_modos", True) else cfg.get("perfiles_modo", {}).get("game", cfg)
            datos["sync_modos"] = cfg.get("sync_modos", True)
            for k in ("curva", "tdp_manual", "tdp", "tdp_boost", "perfil", "boost", "bateria_80", "rgb_modo", "rgb", "rgb_brillo", "rgb_vel", "modo_fan", "fan_pct", "vincular_fans", "cpu_pct", "gpu_pct"):
                if k in fuente:
                    datos[k] = fuente[k]
    except Exception:
        pass
    return json.dumps(datos)

def cargar_bloque_i18n():
    """Lee ui/i18n.js una única vez al arrancar y devuelve el bloque JS STRINGS y el idioma del sistema."""
    ruta_i18n = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui", "i18n.js"))
    try:
        with open(ruta_i18n, "r", encoding="utf-8") as f:
            contenido = f.read()
        inicio = contenido.index("var STRINGS = ")
        fin = contenido.index("function detectarIdioma")
        bloque_strings = contenido[inicio:fin].strip()
    except Exception:
        bloque_strings = "var STRINGS = { en: {} };"

    locale_sys = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "en"
    lang = locale_sys.lower()[:2]
    return lang, bloque_strings

LANG_UI, JS_STRINGS_I18N = cargar_bloque_i18n()



JS_INJECT = """
(() => {
    document.getElementById("ally-center-qam-section")?.remove();
    if (window.__allyObs) window.__allyObs.disconnect();

    __JS_STRINGS_I18N__
    const ALLY_DICT = STRINGS["__LANG_UI__"] || STRINGS["en"] || {};
    const ALLY_FALLBACK = STRINGS["en"] || {};
    const t = (k) => ALLY_DICT[k] || ALLY_FALLBACK[k] || k;
    const TEMPS = Array.of(30, 40, 50, 60, 70, 80, 90, 100);
    const CURVA_DEF = Array.of(15, 25, 40, 55, 70, 85, 95, 100);
    let estado = {
        modelo: "Center ROG Ally X",
        sync_modos: true,
        perfil: 2,
        tdp_manual: false,
        tdp: 30,
        tdp_boost: false,
        boost: false,
        bateria_80: true,
        ac_conectado: true,
        bat_pct: 100,
        bat_watts: "0.0",
        bat_tiempo: "AC",
        temp: "--",
        watts: "--",
        cpu_rpm: 0,
        gpu_rpm: 0,
        curva: CURVA_DEF.slice(),
        modo_fan: "auto",
        fan_pct: 50,
        vincular_fans: true,
        cpu_pct: 50,
        gpu_pct: 50,
        rgb_modo: "fijo",
        rgb: Array.of(0, 210, 255),
        rgb_brillo: 80,
        rgb_brillo_previo: 80
    };

    let tabActiva = "tdp";
    let menuPerfilAbierto = false;
    let curvaTodosJuntos = false;

    function enviarComando(obj) {
        if (obj.cmd !== "estado") {
            window.__allyUltimaEdicion = Date.now();
        }
        if (typeof window.allyBridgeSend === "function") {
            window.allyBridgeSend(JSON.stringify(obj));
        }
    }

    function tdpPorPerfil(perfil, ac) {
        if (perfil === 0) return 13;
        if (perfil === 1) return 17;
        return ac ? 30 : 25;
    }

    function crearSeccionAlly() {
        const box = document.createElement("div");
        box.id = "ally-center-qam-section";
        box.style.cssText = "background: rgba(14, 20, 27, 0.94); border: 1px solid rgba(102, 192, 244, 0.28); border-radius: 10px; padding: 12px; width: 100%; box-sizing: border-box; margin: 14px 0 24px 0; color: #dcdedf; font-family: Motiva Sans, Arial, sans-serif; user-select: none;";
        box.innerHTML = `

            <style>
                #ally-center-qam-section input[type="range"] {
                    -webkit-appearance: none;
                    appearance: none;
                    height: 6px;
                    background: #2a475e;
                    border-radius: 4px;
                    outline: none;
                }
                #ally-center-qam-section input[type="range"]::-webkit-slider-thumb {
                    -webkit-appearance: none;
                    appearance: none;
                    width: 22px;
                    height: 22px;
                    border-radius: 50%;
                    background: #66c0f4;
                    border: 2px solid #ffffff;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.6);
                    cursor: pointer;
                }
            </style>

            <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: flex-end; align-items: center; gap: 6px;">
                    <button id="ally-btn-sync-modos" style="font-size: 10.5px; font-weight: 800; padding: 3px 8px; border-radius: 5px; cursor: pointer; border: 1px solid #66c0f4; background: rgba(102, 192, 244, 0.18); color: #66c0f4;">🔗 ${t("sync_on")}</button>
                    <span id="ally-tel-ac" style="font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 5px; background: rgba(88, 214, 141, 0.18); border: 1px solid #58d68d; color: #58d68d; letter-spacing: 0.4px;">🔌 AC · 80%</span>
                </div>
                <div style="background: #1b2838; border-radius: 6px; padding: 6px 10px; display: flex; align-items: center;">
                    <span id="ally-tel-modelo" style="font-weight: 700; font-size: 13px; color: #66c0f4;">⚡ ${estado.modelo}</span>
                </div>
            </div>

            <div style="background: #1b2838; border-radius: 6px; padding: 7px 6px; margin-bottom: 10px;">
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; text-align: center;">
                    <div>
                        <div style="font-size: 10px; color: #8b929a;">CPU</div>
                        <strong id="ally-tel-cpu" style="font-size: 11px; color: #d6eaf8;">0 RPM</strong>
                    </div>
                    <div>
                        <div style="font-size: 10px; color: #8b929a;">GPU</div>
                        <strong id="ally-tel-gpu" style="font-size: 11px; color: #d6eaf8;">0 RPM</strong>
                    </div>
                    <div>
                        <div style="font-size: 10px; color: #8b929a;">APU</div>
                        <strong id="ally-tel-temp" style="font-size: 11px; color: #f5b041;">-- °C</strong>
                    </div>
                    <div>
                        <div style="font-size: 10px; color: #8b929a;">Chip</div>
                        <strong id="ally-tel-watts" style="font-size: 11px; color: #58d68d;">-- W</strong>
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.07); margin-top: 6px; padding-top: 5px; font-size: 11px;">
                    <span style="color: #8b929a;"><span id="ally-tel-bat-lbl">🔋 ${t("consumption")}:</span> <strong id="ally-tel-bat-watts" style="color: #dcdedf;">0.0 W</strong></span>
                    <span style="color: #8b929a;"><span id="ally-tel-tiempo-lbl">${t("remaining")}:</span> <strong id="ally-tel-bat-tiempo" style="color: #66c0f4;">AC</strong></span>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1.35fr 1fr; gap: 5px; margin-bottom: 11px;">
                <button class="ally-subtab" data-tab="tdp" style="display: flex; align-items: center; justify-content: center; gap: 5px; padding: 6px 6px; border-radius: 6px; font-size: 11.5px; font-weight: 700; cursor: pointer; border: 1px solid #66c0f4; background: #2a475e; color: #fff; white-space: nowrap;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 12l4-4"/><path d="M7.5 16.5a6.5 6.5 0 1 1 9 0"/></svg>
                    <span>${t("tab_tdp")}</span>
                </button>
                <button class="ally-subtab" data-tab="fan" style="display: flex; align-items: center; justify-content: center; gap: 5px; padding: 6px 6px; border-radius: 6px; font-size: 11.5px; font-weight: 700; cursor: pointer; border: 1px solid transparent; background: #1b2838; color: #8b929a; white-space: nowrap;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 10.2a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6zm0-8.2c2.5 0 4.2 1.8 3.6 4.1-.4 1.5-1.5 2.4-2.5 3 .9.2 1.8.8 2.2 1.7 1.3-.8 2.9-1.1 4.4-.2 2.1 1.2 2.4 3.6.7 5.2-1.1 1-2.6 1.1-3.8.5-.3.9-.9 1.6-1.8 2 .3 1.5-.1 3.1-1.6 3.9-2.1 1.1-4.5.1-5.1-2.1-.4-1.4.1-2.8 1-3.7-.7-.6-1.1-1.5-1.1-2.5-1.5.2-3.1-.4-3.7-2-.9-2.2.4-4.5 2.7-4.8 1.4-.2 2.7.5 3.4 1.5.6-.7 1.5-1.1 2.5-1.1-.1-1.5.6-3.1 2.2-3.6.4-.1.8-.2 1.3-.2z"/></svg>
                    <span>${t("tab_fans")}</span>
                </button>
                <button class="ally-subtab" data-tab="rgb" style="display: flex; align-items: center; justify-content: center; gap: 5px; padding: 6px 6px; border-radius: 6px; font-size: 11.5px; font-weight: 700; cursor: pointer; border: 1px solid transparent; background: #1b2838; color: #8b929a; white-space: nowrap;">
                    <svg width="14" height="14" viewBox="0 0 24 24"><defs><linearGradient id="allyRgbGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ff3b30"/><stop offset="35%" stop-color="#ffcc00"/><stop offset="68%" stop-color="#34c759"/><stop offset="100%" stop-color="#007aff"/></linearGradient></defs><circle cx="12" cy="12" r="9" fill="url(#allyRgbGrad)"/><circle cx="12" cy="12" r="3.2" fill="#1b2838"/></svg>
                    <span>${t("tab_rgb")}</span>
                </button>
            </div>

            <div id="ally-pane-tdp" style="background: #1b2838; border-radius: 8px; padding: 10px;">
                <div id="ally-perfil-wrapper" style="position: relative; margin-bottom: 10px;">
                    <div id="ally-row-perfil" style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; cursor: pointer;">
                        <span>${t("power_profile")}</span>
                        <span id="ally-perfil-badge" style="background: #2a475e; border: 1px solid #66c0f4; color: #fff; border-radius: 5px; padding: 5px 10px; font-weight: 600; font-size: 12px;">${t("performance")} (30W) ▾</span>
                    </div>
                    <div id="ally-perfil-menu" style="display: none; position: absolute; right: 0; top: 32px; width: 185px; background: #171d25; border: 1px solid #66c0f4; border-radius: 6px; z-index: 9999; overflow: hidden; box-shadow: 0 6px 16px rgba(0,0,0,0.75);">
                        <div class="ally-perfil-opt" data-val="0" style="padding: 9px 12px; font-size: 12px; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.08);">${t("quiet")} (13W)</div>
                        <div class="ally-perfil-opt" data-val="1" style="padding: 9px 12px; font-size: 12px; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.08);">${t("balanced")} (17W)</div>
                        <div class="ally-perfil-opt" data-val="2" style="padding: 9px 12px; font-size: 12px; cursor: pointer;">${t("performance")} (30W)</div>
                    </div>
                </div>

                <div id="ally-row-manual" style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 8px; cursor: pointer; padding: 3px 0;">
                    <span>${t("manual_tdp_limit")}</span>
                    <span id="ally-manual-badge" style="background: #2a475e; color: #fff; border-radius: 4px; padding: 4px 10px; font-weight: 700; font-size: 11px;">OFF</span>
                </div>
                <div id="ally-manual-box" style="opacity: 0.4; pointer-events: none; transition: opacity 0.15s; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
                        <span>${t("tdp_limit")}</span>
                        <strong id="ally-tdp-val" style="color: #66c0f4;">30 W</strong>
                    </div>
                    <input id="ally-tdp-slider" type="range" min="7" max="30" value="30" style="width: 100%; accent-color: #66c0f4; height: 22px; margin-bottom: 8px; cursor: pointer;">
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-bottom: 8px;">
                        <button class="ally-preset-btn" data-w="13" style="background: #1b2838; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">13W</button>
                        <button class="ally-preset-btn" data-w="17" style="background: #1b2838; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">17W</button>
                        <button class="ally-preset-btn" data-w="25" style="background: #1b2838; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">25W</button>
                        <button id="ally-preset-30" class="ally-preset-btn" data-w="30" style="background: #1b2838; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">30W</button>
                    </div>
                    <div id="ally-row-tdp-boost" style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; cursor: pointer; padding: 3px 0;">
                        <span>${t("sppt_fppt_boost")}</span>
                        <span id="ally-tdp-boost-badge" style="background: #2a475e; color: #fff; border-radius: 4px; padding: 4px 10px; font-weight: 700; font-size: 11px;">OFF</span>
                    </div>
                </div>

                <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; display: flex; flex-direction: column; gap: 6px;">
                    <div id="ally-row-boost" style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; cursor: pointer; padding: 3px 0;">
                        <span>CPU Boost</span>
                        <span id="ally-boost-badge" style="background: #2a475e; color: #fff; border-radius: 4px; padding: 4px 10px; font-weight: 700; font-size: 11px;">OFF</span>
                    </div>
                    <div id="ally-row-bat80" style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; cursor: pointer; padding: 3px 0;">
                        <span>${t("battery_care")}</span>
                        <span id="ally-bat80-badge" style="background: #66c0f4; color: #0e141b; border-radius: 4px; padding: 4px 10px; font-weight: 700; font-size: 11px;">ON</span>
                    </div>
                </div>
            </div>

            <div id="ally-pane-fan" style="display: none; background: #1b2838; border-radius: 8px; padding: 10px;">
                <div style="position: relative; margin-bottom: 10px;">
                    <div id="ally-row-fan-modo" style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; cursor: pointer;">
                        <span>${t("mode")}</span>
                        <span id="ally-fan-modo-badge" style="background: #2a475e; border: 1px solid #66c0f4; color: #fff; border-radius: 5px; padding: 5px 10px; font-weight: 600; font-size: 12px;">${t("fan_auto_bios")} ▾</span>
                    </div>
                    <div id="ally-fan-modo-menu" style="display: none; position: absolute; right: 0; top: 32px; width: 195px; background: #171d25; border: 1px solid #66c0f4; border-radius: 6px; z-index: 9999; overflow: hidden; box-shadow: 0 6px 16px rgba(0,0,0,0.75);">
                        <div class="ally-fan-modo-opt" data-modo="auto" style="padding: 9px 12px; font-size: 12px; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.08);">${t("fan_auto_bios")}</div>
                        <div class="ally-fan-modo-opt" data-modo="manual" style="padding: 9px 12px; font-size: 12px; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.08);">${t("fan_manual_profiles")}</div>
                        <div class="ally-fan-modo-opt" data-modo="curva" style="padding: 9px 12px; font-size: 12px; cursor: pointer;">${t("fan_custom_curve")}</div>
                    </div>
                </div>

                <div id="ally-fan-sub-auto" style="font-size: 11px; color: #8b929a; text-align: center; padding: 10px 4px;">
                    ${t("fan_auto_desc")}
                </div>

                <div id="ally-fan-sub-manual" style="display: none;">
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin-bottom: 10px;">
                        <button class="ally-fan-preset" data-pct="30" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("fan_quiet")}</button>
                        <button class="ally-fan-preset" data-pct="60" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("fan_balanced")}</button>
                        <button class="ally-fan-preset" data-pct="90" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("fan_turbo")}</button>
                    </div>

                    <div id="ally-row-vincular" style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 8px; cursor: pointer; padding: 3px 0;">
                        <span>${t("link_cpu_gpu")}</span>
                        <span id="ally-vincular-badge" style="background: #66c0f4; color: #0e141b; border-radius: 4px; padding: 4px 10px; font-weight: 700; font-size: 11px;">ON</span>
                    </div>

                    <div id="ally-fan-ambos-box">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
                            <span>${t("both")}</span>
                            <strong id="ally-fan-ambos-val" style="color: #66c0f4;">50%</strong>
                        </div>
                        <input id="ally-fan-ambos-slider" type="range" min="0" max="100" value="50" style="width: 100%; margin: 4px 0;">
                    </div>

                    <div id="ally-fan-sep-box" style="display: none; flex-direction: column; gap: 10px;">
                        <div>
                            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
                                <span>CPU Fan</span>
                                <strong id="ally-fan-cpu-val" style="color: #66c0f4;">50%</strong>
                            </div>
                            <input id="ally-fan-cpu-slider" type="range" min="0" max="100" value="50" style="width: 100%; margin: 4px 0;">
                        </div>
                        <div>
                            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
                                <span>GPU Fan</span>
                                <strong id="ally-fan-gpu-val" style="color: #66c0f4;">50%</strong>
                            </div>
                            <input id="ally-fan-gpu-slider" type="range" min="0" max="100" value="50" style="width: 100%; margin: 4px 0;">
                        </div>
                    </div>
                </div>

                <div id="ally-fan-sub-curva" style="display: none;">
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin-bottom: 8px;">
                        <button class="ally-curva-preset" data-pts="5,10,15,20,30,40,50,60" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 6px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("fan_quiet")}</button>
                        <button class="ally-curva-preset" data-pts="15,25,40,55,70,85,95,100" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 6px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("fan_balanced")}</button>
                        <button class="ally-curva-preset" data-pts="30,45,60,75,90,100,100,100" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 6px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("fan_turbo")}</button>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-size: 12px; font-weight: 700;">${t("curve_points")}</span>
                        <div style="display: flex; gap: 6px;">
                            <button id="ally-btn-curva-reset" title="${t("reset_curve_tip")}" style="background: #2a475e; color: #fff; border: none; border-radius: 4px; padding: 5px 9px; font-size: 12px; font-weight: 700; cursor: pointer;">↺</button>
                            <button id="ally-row-curva-modo" style="background: #2a475e; color: #fff; border: none; border-radius: 4px; padding: 5px 10px; font-size: 11px; font-weight: 700; cursor: pointer;">${t("cascade")}</button>
                        </div>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        ${TEMPS.map((temp, i) => `
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="width: 36px; font-size: 11px; color: #8b929a;">${temp}°C</span>
                                <input class="ally-pt" data-idx="${i}" type="range" min="0" max="100" value="${CURVA_DEF.at(i)}" style="flex: 1;">
                                <span class="ally-pt-val" style="width: 34px; text-align: right; font-size: 11px; font-weight: 600;">${CURVA_DEF.at(i)}%</span>
                            </div>
                        `).join("")}
                    </div>
                </div>
            </div>

            <div id="ally-pane-rgb" style="display: none; background: #1b2838; border-radius: 8px; padding: 10px;">
                <div id="ally-row-rgb-activo" style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 10px; cursor: pointer; padding: 2px 0;">
                    <span style="font-weight: 700;">${t("led_lighting")}</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span id="ally-rgb-circulo" style="width: 20px; height: 20px; border-radius: 50%; border: 1.5px solid #fff; background: rgb(0,210,255); display: inline-block; box-sizing: border-box;"></span>
                        <span id="ally-rgb-activo-badge" style="background: #66c0f4; color: #0e141b; border-radius: 4px; padding: 4px 10px; font-weight: 700; font-size: 11px;">ON</span>
                    </div>
                </div>

                <div id="ally-rgb-controles" style="transition: opacity 0.15s;">
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin-bottom: 10px;">
                        <button class="ally-rgb-cat-btn" data-cat="fijo" style="background: #66c0f4; color: #0e141b; border: 1px solid #66c0f4; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_fixed")}</button>
                        <button class="ally-rgb-cat-btn" data-cat="efectos" style="background: #0e141b; color: #8b929a; border: 1px solid #2a475e; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_effects")}</button>
                        <button class="ally-rgb-cat-btn" data-cat="sensores" style="background: #0e141b; color: #8b929a; border: 1px solid #2a475e; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_sensors")}</button>
                    </div>

                    <div id="ally-rgb-sec-efectos" style="display: none; flex-direction: column; gap: 8px; margin-bottom: 10px;">
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px;">
                            <button class="ally-rgb-modo-btn" data-modo="respiracion" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_breathing")}</button>
                            <button class="ally-rgb-modo-btn" data-modo="ciclo" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_color_cycle")}</button>
                            <button class="ally-rgb-modo-btn" data-modo="arcoiris" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_rainbow")}</button>
                        </div>

                        <div>
                            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
                                <span>${t("speed")}</span>
                                <strong id="ally-rgb-vel-val" style="color: #66c0f4;">${t("medium")}</strong>
                            </div>
                            <input id="ally-rgb-vel" type="range" min="1" max="3" step="1" value="2" style="width: 100%; margin: 4px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; font-size: 10px; color: #8b929a; margin-top: 2px;">
                                <div style="display: flex; flex-direction: column; align-items: flex-start;">
                                    <span style="width: 1px; height: 5px; background: #66c0f4; margin-bottom: 2px; margin-left: 8px;"></span>
                                    <span>${t("slow")}</span>
                                </div>
                                <span style="width: 1px; height: 5px; background: #4f6478;"></span>
                                <div style="display: flex; flex-direction: column; align-items: flex-end;">
                                    <span style="width: 1px; height: 5px; background: #4f6478; margin-bottom: 2px; margin-right: 8px;"></span>
                                    <span>${t("fast")}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div id="ally-rgb-sec-sensores" style="display: none; grid-template-columns: repeat(3, 1fr); gap: 5px; margin-bottom: 10px;">
                        <button class="ally-rgb-modo-btn" data-modo="temp" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_temp_short")}</button>
                        <button class="ally-rgb-modo-btn" data-modo="bateria" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_bat_short")}</button>
                        <button class="ally-rgb-modo-btn" data-modo="hora" style="background: #0e141b; border: 1px solid #3d5a73; color: #fff; border-radius: 5px; padding: 7px 0; font-size: 11px; font-weight: 700; cursor: pointer;">${t("rgb_time_short")}</button>
                    </div>

                    <div id="ally-rgb-colores-box" style="margin-bottom: 10px;">
                        <div style="font-size: 11px; color: #8b929a; margin-bottom: 6px;">${t("quick_colors")}</div>
                        <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px;">
                            <button class="ally-rgb-swatch" data-rgb="255,0,0" style="height: 26px; border-radius: 5px; border: 1px solid #444; background: rgb(255,0,0); cursor: pointer;"></button>
                            <button class="ally-rgb-swatch" data-rgb="0,210,255" style="height: 26px; border-radius: 5px; border: 2px solid #fff; background: rgb(0,210,255); cursor: pointer;"></button>
                            <button class="ally-rgb-swatch" data-rgb="165,40,255" style="height: 26px; border-radius: 5px; border: 1px solid #444; background: rgb(165,40,255); cursor: pointer;"></button>
                            <button class="ally-rgb-swatch" data-rgb="0,255,0" style="height: 26px; border-radius: 5px; border: 1px solid #444; background: rgb(0,255,0); cursor: pointer;"></button>
                            <button class="ally-rgb-swatch" data-rgb="255,110,0" style="height: 26px; border-radius: 5px; border: 1px solid #444; background: rgb(255,110,0); cursor: pointer;"></button>
                            <button class="ally-rgb-swatch" data-rgb="255,165,0" style="height: 26px; border-radius: 5px; border: 1px solid #444; background: rgb(255,165,0); cursor: pointer;"></button>
                            <button class="ally-rgb-swatch" data-rgb="255,255,255" style="height: 26px; border-radius: 5px; border: 1px solid #444; background: rgb(255,255,255); cursor: pointer;"></button>
                        </div>
                    </div>

                    <div id="ally-rgb-brillo-box">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
                            <span>${t("led_brightness")}</span>
                            <strong id="ally-rgb-brillo-val" style="color: #66c0f4;">80%</strong>
                        </div>
                        <input id="ally-rgb-brillo" type="range" min="5" max="100" step="5" value="80" style="width: 100%; margin: 4px 0;">
                        <div id="ally-rgb-brillo-ticks" style="display: flex; justify-content: space-between; padding: 0 8px; margin-top: 2px;">
                            ${Array.from({length: 20}, (_, i) => '<span class="ally-brillo-tick" data-idx="' + i + '" style="width: 1px; height: 5px; background: #4f6478;"></span>').join("")}
                        </div>
                    </div>
                </div>
            </div>
        `;

        box.querySelectorAll(".ally-subtab").forEach(btn => {
            btn.onclick = () => {
                tabActiva = btn.dataset.tab;
                box.querySelectorAll(".ally-subtab").forEach(b => {
                    const activo = b.dataset.tab === tabActiva;
                    b.style.background = activo ? "#2a475e" : "#1b2838";
                    b.style.color = activo ? "#fff" : "#8b929a";
                    b.style.borderColor = activo ? "#66c0f4" : "transparent";
                });
                box.querySelector("#ally-pane-tdp").style.display = tabActiva === "tdp" ? "block" : "none";
                box.querySelector("#ally-pane-fan").style.display = tabActiva === "fan" ? "block" : "none";
                box.querySelector("#ally-pane-rgb").style.display = tabActiva === "rgb" ? "block" : "none";
            };
        });

        const rowPerfil = box.querySelector("#ally-row-perfil");
        const menuPerfil = box.querySelector("#ally-perfil-menu");
        rowPerfil.onclick = (e) => {
            e.stopPropagation();
            if (estado.tdp_manual) return;
            menuPerfilAbierto = !menuPerfilAbierto;
            menuPerfil.style.display = menuPerfilAbierto ? "block" : "none";
        };
        box.querySelectorAll(".ally-perfil-opt").forEach(opt => {
            opt.onclick = (e) => {
                e.stopPropagation();
                const val = parseInt(opt.dataset.val);
                estado.perfil = val;
                estado.tdp = tdpPorPerfil(val, estado.ac_conectado);
                menuPerfilAbierto = false;
                menuPerfil.style.display = "none";
                actualizarUI();
                enviarComando({ cmd: "perfil", val });
            };
        });

        box.querySelector("#ally-row-manual").onclick = () => {
            estado.tdp_manual = !estado.tdp_manual;
            if (!estado.tdp_manual) {
                estado.tdp = tdpPorPerfil(estado.perfil, estado.ac_conectado);
                estado.tdp_boost = false;
                actualizarUI();
                enviarComando({ cmd: "perfil", val: estado.perfil });
            } else {
                actualizarUI();
                enviarComando({ cmd: "tdp", val: estado.tdp, boost_pico: estado.tdp_boost ? 1 : 0 });
            }
        };

        const tdpSlider = box.querySelector("#ally-tdp-slider");
        const setTdp = (w) => {
            const maxW = estado.ac_conectado ? 30 : 25;
            w = Math.max(7, Math.min(maxW, w));
            estado.tdp = w;
            if (w < 25) estado.tdp_boost = false;
            actualizarUI();
            enviarComando({ cmd: "tdp", val: w, boost_pico: estado.tdp_boost ? 1 : 0 });
        };
        tdpSlider.oninput = () => setTdp(parseInt(tdpSlider.value));
        box.querySelectorAll(".ally-preset-btn").forEach(btn => {
            btn.onclick = () => {
                if (!estado.tdp_manual) estado.tdp_manual = true;
                setTdp(parseInt(btn.dataset.w));
            };
        });
        box.querySelector("#ally-row-tdp-boost").onclick = () => {
            if (!estado.tdp_manual || estado.tdp < 25) return;
            estado.tdp_boost = !estado.tdp_boost;
            actualizarUI();
            enviarComando({ cmd: "tdp", val: estado.tdp, boost_pico: estado.tdp_boost ? 1 : 0 });
        };

        box.querySelector("#ally-row-boost").onclick = () => {
            estado.boost = !estado.boost;
            actualizarUI();
            enviarComando({ cmd: "cpu_boost", val: estado.boost ? 1 : 0 });
        };

        box.querySelector("#ally-row-bat80").onclick = () => {
            estado.bateria_80 = !estado.bateria_80;
            actualizarUI();
            enviarComando({ cmd: "bateria", val: estado.bateria_80 ? 1 : 0 });
        };

        // Selector de Modo Ventiladores (Automático / Manual / Curva)
        let menuFanModoAbierto = false;
        const rowFanModo = box.querySelector("#ally-row-fan-modo");
        const menuFanModo = box.querySelector("#ally-fan-modo-menu");
        rowFanModo.onclick = (e) => {
            e.stopPropagation();
            menuFanModoAbierto = !menuFanModoAbierto;
            menuFanModo.style.display = menuFanModoAbierto ? "block" : "none";
        };
        box.querySelectorAll(".ally-fan-modo-opt").forEach(opt => {
            opt.onclick = (e) => {
                e.stopPropagation();
                const m = opt.dataset.modo;
                estado.modo_fan = m;
                menuFanModoAbierto = false;
                menuFanModo.style.display = "none";
                actualizarUI();
                if (m === "auto") {
                    enviarComando({ cmd: "fan_auto" });
                } else if (m === "manual") {
                    if (estado.vincular_fans) {
                        enviarComando({ cmd: "fan_ambos", val: estado.fan_pct });
                    } else {
                        enviarComando({ cmd: "fan_sep", cpu: estado.cpu_pct, gpu: estado.gpu_pct });
                    }
                } else if (m === "curva") {
                    enviarComando({ cmd: "guardar_curva", val: estado.curva.slice() });
                }
            };
        });

        // Presets Manuales: Silencioso (30%), Equilibrado (60%), Turbo (90%)
        box.querySelectorAll(".ally-fan-preset").forEach(btn => {
            btn.onclick = () => {
                const pct = parseInt(btn.dataset.pct);
                estado.modo_fan = "manual";
                estado.vincular_fans = true;
                estado.fan_pct = pct;
                estado.cpu_pct = pct;
                estado.gpu_pct = pct;
                actualizarUI();
                enviarComando({ cmd: "fan_ambos", val: pct });
            };
        });

        // Toggle Vincular CPU + GPU
        box.querySelector("#ally-row-vincular").onclick = () => {
            estado.vincular_fans = !estado.vincular_fans;
            actualizarUI();
            if (estado.vincular_fans) {
                enviarComando({ cmd: "fan_ambos", val: estado.fan_pct });
            } else {
                enviarComando({ cmd: "fan_sep", cpu: estado.cpu_pct, gpu: estado.gpu_pct });
            }
        };

        // Sliders Manuales (Ambos / CPU / GPU)
        let timerFanMan = null;
        const slAmbos = box.querySelector("#ally-fan-ambos-slider");
        slAmbos.oninput = () => {
            const pct = parseInt(slAmbos.value);
            estado.fan_pct = pct;
            estado.cpu_pct = pct;
            estado.gpu_pct = pct;
            actualizarUI();
            clearTimeout(timerFanMan);
            timerFanMan = setTimeout(() => enviarComando({ cmd: "fan_ambos", val: pct }), 150);
        };
        const slCpu = box.querySelector("#ally-fan-cpu-slider");
        slCpu.oninput = () => {
            estado.cpu_pct = parseInt(slCpu.value);
            actualizarUI();
            clearTimeout(timerFanMan);
            timerFanMan = setTimeout(() => enviarComando({ cmd: "fan_sep", cpu: estado.cpu_pct, gpu: estado.gpu_pct }), 150);
        };
        const slGpu = box.querySelector("#ally-fan-gpu-slider");
        slGpu.oninput = () => {
            estado.gpu_pct = parseInt(slGpu.value);
            actualizarUI();
            clearTimeout(timerFanMan);
            timerFanMan = setTimeout(() => enviarComando({ cmd: "fan_sep", cpu: estado.cpu_pct, gpu: estado.gpu_pct }), 150);
        };

        const btnModoCurva = box.querySelector("#ally-row-curva-modo");
        btnModoCurva.onclick = () => {
            curvaTodosJuntos = !curvaTodosJuntos;
            btnModoCurva.textContent = curvaTodosJuntos ? t("all_together") : t("cascade");
            btnModoCurva.style.background = curvaTodosJuntos ? "#66c0f4" : "#2a475e";
            btnModoCurva.style.color = curvaTodosJuntos ? "#0e141b" : "#fff";
        };
        box.querySelector("#ally-btn-curva-reset").onclick = () => {
            estado.curva = CURVA_DEF.slice();
            actualizarUI();
            enviarComando({ cmd: "guardar_curva", val: estado.curva });
        };

        const slidersFan = Array.from(box.querySelectorAll(".ally-pt"));
        let timerFan = null;
        slidersFan.forEach((sl, idx) => {
            sl.oninput = () => {
                const v = parseInt(sl.value);
                if (curvaTodosJuntos) {
                    estado.curva = estado.curva.map(() => v);
                } else {
                    estado.curva.splice(idx, 1, v);
                    for (let j = idx + 1; j < 8; j++) {
                        if (estado.curva.at(j) < v) estado.curva.splice(j, 1, v);
                    }
                    for (let j = idx - 1; j >= 0; j--) {
                        if (estado.curva.at(j) > v) estado.curva.splice(j, 1, v);
                    }
                }
                actualizarUI();
                clearTimeout(timerFan);
                timerFan = setTimeout(() => {
                    enviarComando({ cmd: "guardar_curva", val: estado.curva.slice() });
                }, 180);
            };
        });

        // Presets de Curva Personalizada (Silencioso, Equilibrado, Turbo)
        box.querySelectorAll(".ally-curva-preset").forEach(btn => {
            btn.onclick = () => {
                estado.curva = btn.dataset.pts.split(",").map(Number);
                estado.modo_fan = "curva";
                actualizarUI();
                enviarComando({ cmd: "guardar_curva", val: estado.curva.slice() });
            };
        });

        // Controles RGB (Switch Encendido/Apagado + Selector de Modo + Colores + Brillo 5-100%)
        const aplicarRgb = () => {
            actualizarUI();
            enviarComando({
                cmd: "rgb",
                modo: estado.rgb_modo,
                rgb: estado.rgb,
                brillo: estado.rgb_brillo,
                vel: estado.rgb_vel || 2
            });
        };

        box.querySelector("#ally-row-rgb-activo").onclick = () => {
            if (estado.rgb_brillo > 0) {
                estado.rgb_brillo_previo = estado.rgb_brillo;
                estado.rgb_brillo = 0;
            } else {
                estado.rgb_brillo = Math.max(5, estado.rgb_brillo_previo || 80);
            }
            aplicarRgb();
        };

        box.querySelectorAll(".ally-rgb-cat-btn").forEach(btn => {
            btn.onclick = () => {
                if (estado.rgb_brillo === 0) return;
                const cat = btn.dataset.cat;
                if (cat === "fijo") estado.rgb_modo = "fijo";
                else if (cat === "efectos" && !["respiracion", "ciclo", "arcoiris"].includes(estado.rgb_modo)) estado.rgb_modo = "respiracion";
                else if (cat === "sensores" && !["temp", "bateria", "hora"].includes(estado.rgb_modo)) estado.rgb_modo = "temp";
                aplicarRgb();
            };
        });

        box.querySelectorAll(".ally-rgb-modo-btn").forEach(btn => {
            btn.onclick = () => {
                if (estado.rgb_brillo === 0) return;
                estado.rgb_modo = btn.dataset.modo;
                aplicarRgb();
            };
        });

        box.querySelectorAll(".ally-rgb-swatch").forEach(btn => {
            btn.onclick = () => {
                if (estado.rgb_brillo === 0) return;
                estado.rgb = btn.dataset.rgb.split(",").map(Number);
                if (!["fijo", "respiracion"].includes(estado.rgb_modo)) {
                    estado.rgb_modo = "fijo";
                }
                aplicarRgb();
            };
        });

        const brilloSlider = box.querySelector("#ally-rgb-brillo");
        let timerRgb = null;
        brilloSlider.oninput = () => {
            if (estado.rgb_brillo === 0) return;
            const v = Math.max(5, parseInt(brilloSlider.value));
            estado.rgb_brillo = v;
            estado.rgb_brillo_previo = v;
            actualizarUI();
            clearTimeout(timerRgb);
            timerRgb = setTimeout(aplicarRgb, 150);
        };

        const velSlider = box.querySelector("#ally-rgb-vel");
        velSlider.oninput = () => {
            if (estado.rgb_brillo === 0) return;
            estado.rgb_vel = parseInt(velSlider.value);
            aplicarRgb();
        };

        box.querySelector("#ally-btn-sync-modos").onclick = () => {
            estado.sync_modos = !(estado.sync_modos !== false);
            actualizarUI();
            enviarComando({ cmd: "sync_modos", val: estado.sync_modos ? "1" : "0" });
        };

        return box;

    }
    function actualizarUI() {
        const sec = document.getElementById("ally-center-qam-section");
        if (!sec) return;

        sec.querySelector("#ally-tel-modelo").textContent = `⚡ ${estado.modelo || "Center ROG Ally X"}`;
        const btnSync = sec.querySelector("#ally-btn-sync-modos");
        if (btnSync) {
            const sOn = estado.sync_modos !== false;
            btnSync.textContent = sOn ? `🔗 ${t("sync_on")}` : `🔓 ${t("per_mode")}`;
            btnSync.style.borderColor = sOn ? "#66c0f4" : "#f5b041";
            btnSync.style.background = sOn ? "rgba(102, 192, 244, 0.18)" : "rgba(245, 176, 65, 0.16)";
            btnSync.style.color = sOn ? "#66c0f4" : "#f5b041";
        }
        sec.querySelector("#ally-tel-ac").textContent = estado.ac_conectado ? "AC" : "BAT";
        sec.querySelector("#ally-tel-temp").textContent = `${estado.temp ?? "--"} °C`;
        sec.querySelector("#ally-tel-watts").textContent = `${estado.watts ?? "--"} W`;
        sec.querySelector("#ally-tel-cpu").textContent = `${estado.cpu_rpm ?? 0} RPM`;
        sec.querySelector("#ally-tel-gpu").textContent = `${estado.gpu_rpm ?? 0} RPM`;
        const acEl = sec.querySelector("#ally-tel-ac");
        const pctBat = estado.bat_pct ?? 100;
        if (estado.ac_conectado) {
            acEl.textContent = `🔌 AC · ${pctBat}%`;
            acEl.style.background = "rgba(88, 214, 141, 0.18)";
            acEl.style.borderColor = "#58d68d";
            acEl.style.color = "#58d68d";
        } else {
            acEl.textContent = `🔋 BAT · ${pctBat}%`;
            acEl.style.background = "rgba(245, 176, 65, 0.18)";
            acEl.style.borderColor = "#f5b041";
            acEl.style.color = "#f5b041";
        }
        const batLbl = sec.querySelector("#ally-tel-bat-lbl");
        const batWattsEl = sec.querySelector("#ally-tel-bat-watts");
        const tiempoLbl = sec.querySelector("#ally-tel-tiempo-lbl");
        const tiempoEl = sec.querySelector("#ally-tel-bat-tiempo");
        const wBat = parseFloat(estado.bat_watts || "0");

    if (estado.ac_conectado && wBat < 0.5) {
         batLbl.textContent = `🔋 ${t("battery")}:`;
         batWattsEl.textContent = estado.bateria_80 ? t("limit_80") : t("full");
         batWattsEl.style.color = "#58d68d";
         tiempoLbl.textContent = `${t("status")}:`;
         tiempoEl.textContent = t("idle");
         tiempoEl.style.color = "#58d68d";
     } else if (estado.ac_conectado) {
         batLbl.textContent = `⚡ ${t("charging")}:`;
         batWattsEl.textContent = `+${estado.bat_watts} W`;
         batWattsEl.style.color = "#66c0f4";
         tiempoLbl.textContent = `${t("status")}:`;
         tiempoEl.textContent = t("in_charge");
         tiempoEl.style.color = "#66c0f4";
     } else {
         batLbl.textContent = `🔋 ${t("consumption")}:`;
         batWattsEl.textContent = `${estado.bat_watts ?? "0.0"} W`;
         batWattsEl.style.color = "#dcdedf";
         tiempoLbl.textContent = `${t("remaining")}:`;
         tiempoEl.textContent = estado.bat_tiempo || "--";
         tiempoEl.style.color = "#66c0f4";
     }
     const pMax = estado.ac_conectado ? "30W" : "25W";
     const nombres = { 0: `${t("quiet")} (13W)`, 1: `${t("balanced")} (17W)`, 2: `${t("performance")} (${pMax})` };
     sec.querySelector("#ally-perfil-badge").textContent = (nombres[estado.perfil] ?? `${t("performance")} (${pMax})`) + " ▾";
     const optRend = sec.querySelector('.ally-perfil-opt[data-val="2"]');
     if (optRend) optRend.textContent = `${t("performance")} (${pMax})`;
        const manualOn = Boolean(estado.tdp_manual);
        const mBadge = sec.querySelector("#ally-manual-badge");
        mBadge.textContent = manualOn ? "ON" : "OFF";
        mBadge.style.background = manualOn ? "#66c0f4" : "#2a475e";
        mBadge.style.color = manualOn ? "#0e141b" : "#fff";
        const mBox = sec.querySelector("#ally-manual-box");
        mBox.style.opacity = manualOn ? "1" : "0.4";
        mBox.style.pointerEvents = manualOn ? "auto" : "none";
        const pWrap = sec.querySelector("#ally-perfil-wrapper");
        pWrap.style.opacity = manualOn ? "0.4" : "1";
        pWrap.style.pointerEvents = manualOn ? "none" : "auto";
        const preset30 = sec.querySelector("#ally-preset-30");
        if (preset30) preset30.style.display = estado.ac_conectado ? "block" : "none";
        const maxActual = estado.ac_conectado ? 30 : 25;
        if (!manualOn) {
            estado.tdp = tdpPorPerfil(estado.perfil, estado.ac_conectado);
        } else if (estado.tdp > maxActual) {
            estado.tdp = maxActual;
        }
        const tdpS = sec.querySelector("#ally-tdp-slider");
        tdpS.max = maxActual;
        tdpS.value = estado.tdp;
        sec.querySelector("#ally-tdp-val").textContent = `${estado.tdp} W`;

        const tbHabilitado = manualOn && estado.tdp >= 25;
        const tbActivo = tbHabilitado && Boolean(estado.tdp_boost);
        const tbRow = sec.querySelector("#ally-row-tdp-boost");
        const tbBadge = sec.querySelector("#ally-tdp-boost-badge");
        tbRow.style.opacity = tbHabilitado ? "1" : "0.4";
        tbRow.style.pointerEvents = tbHabilitado ? "auto" : "none";
        tbBadge.textContent = tbActivo ? "ON" : "OFF";
        tbBadge.style.background = tbActivo ? "#66c0f4" : "#2a475e";
        tbBadge.style.color = tbActivo ? "#0e141b" : "#fff";

        const bBadge = sec.querySelector("#ally-boost-badge");
        bBadge.textContent = estado.boost ? "ON" : "OFF";
        bBadge.style.background = estado.boost ? "#66c0f4" : "#2a475e";
        bBadge.style.color = estado.boost ? "#0e141b" : "#fff";

        const batBadge = sec.querySelector("#ally-bat80-badge");
        batBadge.textContent = estado.bateria_80 ? "ON" : "OFF";
        batBadge.style.background = estado.bateria_80 ? "#66c0f4" : "#2a475e";
        batBadge.style.color = estado.bateria_80 ? "#0e141b" : "#fff";


        const modoFan = estado.modo_fan || "auto";
        const nombresFan = { auto: t("fan_auto_bios"), manual: t("fan_manual_profiles"), curva: t("fan_custom_curve") };
        sec.querySelector("#ally-fan-modo-badge").textContent = (nombresFan[modoFan] || t("fan_auto_bios")) + " ▾";
        sec.querySelector("#ally-fan-sub-auto").style.display = modoFan === "auto" ? "block" : "none";
        sec.querySelector("#ally-fan-sub-manual").style.display = modoFan === "manual" ? "block" : "none";
        sec.querySelector("#ally-fan-sub-curva").style.display = modoFan === "curva" ? "block" : "none";

        const vincOn = Boolean(estado.vincular_fans);
        const vincBadge = sec.querySelector("#ally-vincular-badge");
        vincBadge.textContent = vincOn ? "ON" : "OFF";
        vincBadge.style.background = vincOn ? "#66c0f4" : "#2a475e";
        vincBadge.style.color = vincOn ? "#0e141b" : "#fff";
        sec.querySelector("#ally-fan-ambos-box").style.display = vincOn ? "block" : "none";
        sec.querySelector("#ally-fan-sep-box").style.display = vincOn ? "none" : "flex";

        const pctAmbos = estado.fan_pct ?? 50;
        sec.querySelector("#ally-fan-ambos-slider").value = pctAmbos;
        sec.querySelector("#ally-fan-ambos-val").textContent = `${pctAmbos}%`;
        sec.querySelector("#ally-fan-cpu-slider").value = estado.cpu_pct ?? pctAmbos;
        sec.querySelector("#ally-fan-cpu-val").textContent = `${estado.cpu_pct ?? pctAmbos}%`;
        sec.querySelector("#ally-fan-gpu-slider").value = estado.gpu_pct ?? pctAmbos;
        sec.querySelector("#ally-fan-gpu-val").textContent = `${estado.gpu_pct ?? pctAmbos}%`;

        if (Array.isArray(estado.curva) && estado.curva.length === 8) {
            const vals = sec.querySelectorAll(".ally-pt-val");
            sec.querySelectorAll(".ally-pt").forEach((sl, i) => {
                sl.value = estado.curva.at(i);
                if (vals.item(i)) vals.item(i).textContent = `${estado.curva.at(i)}%`;
            });
        }

        const rgbOn = (estado.rgb_brillo ?? 80) > 0;
        if (rgbOn) estado.rgb_brillo_previo = estado.rgb_brillo;
        const rgbActBadge = sec.querySelector("#ally-rgb-activo-badge");
        rgbActBadge.textContent = rgbOn ? "ON" : "OFF";
        rgbActBadge.style.background = rgbOn ? "#66c0f4" : "#2a475e";
        rgbActBadge.style.color = rgbOn ? "#0e141b" : "#fff";

        const rgbCtrl = sec.querySelector("#ally-rgb-controles");
        rgbCtrl.style.opacity = rgbOn ? "1" : "0.4";
        rgbCtrl.style.pointerEvents = rgbOn ? "auto" : "none";

        const modoRgb = estado.rgb_modo || "fijo";
        const circEl = sec.querySelector("#ally-rgb-circulo");
        if (circEl) {
            if (!document.getElementById("ally-rgb-anim-style")) {
                const st = document.createElement("style");
                st.id = "ally-rgb-anim-style";
                st.textContent = "@keyframes allySpin { to { transform: rotate(360deg); } } @keyframes allyPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }";
                document.head.appendChild(st);
            }
            const velAct = estado.rgb_vel || 2;
            const durSpin = velAct === 1 ? "4.5s" : (velAct === 3 ? "1.2s" : "2.5s");
            const durPulse = velAct === 1 ? "3.6s" : (velAct === 3 ? "1.1s" : "2.0s");
            const rgbArr = Array.isArray(estado.rgb) && estado.rgb.length === 3 ? estado.rgb : [0, 210, 255];
            const rgbCss = `rgb(${rgbArr[0]}, ${rgbArr[1]}, ${rgbArr[2]})`;

            circEl.style.animation = "none";
            if (!rgbOn) {
                circEl.style.background = "#222222";
            } else if (modoRgb === "ciclo" || modoRgb === "arcoiris") {
                circEl.style.background = "linear-gradient(90deg, #ff0000 0%, #00ff00 33%, #00d2ff 66%, #a528ff 100%)";
                circEl.style.animation = `allySpin ${durSpin} linear infinite`;
            } else if (modoRgb === "respiracion") {
                circEl.style.background = rgbCss;
                circEl.style.animation = `allyPulse ${durPulse} ease-in-out infinite`;
            } else if (modoRgb === "temp") {
                const tempApu = estado.temp ?? 50;
                circEl.style.background = tempApu <= 35 ? "rgb(0,210,255)" : (tempApu <= 65 ? "rgb(0,255,0)" : (tempApu <= 75 ? "rgb(255,165,0)" : (tempApu <= 85 ? "rgb(255,110,0)" : "rgb(255,0,0)")));
            } else if (modoRgb === "bateria") {
                const b = estado.bat_pct ?? 80;
                circEl.style.background = estado.ac_conectado ? "rgb(0,255,0)" : (b > 60 ? "rgb(0,255,0)" : (b >= 25 ? "rgb(255,165,0)" : (b > 10 ? "rgb(255,110,0)" : "rgb(255,0,0)")));
            } else if (modoRgb === "hora") {
                const h = new Date().getHours();
                circEl.style.background = (h >= 7 && h < 13) ? "rgb(255,255,255)" : ((h >= 13 && h < 20) ? "rgb(0,210,255)" : "rgb(255,0,0)");
            } else {
                circEl.style.background = rgbCss;
            }
        }

        const catRgb = ["respiracion", "ciclo", "arcoiris"].includes(modoRgb)
            ? "efectos"
            : (["temp", "bateria", "hora"].includes(modoRgb) ? "sensores" : "fijo");

        sec.querySelectorAll(".ally-rgb-cat-btn").forEach(btn => {
            const act = btn.dataset.cat === catRgb;
            btn.style.background = act ? "#66c0f4" : "#0e141b";
            btn.style.color = act ? "#0e141b" : "#8b929a";
            btn.style.borderColor = act ? "#66c0f4" : "#2a475e";
        });

        sec.querySelector("#ally-rgb-sec-efectos").style.display = catRgb === "efectos" ? "flex" : "none";
        sec.querySelector("#ally-rgb-sec-sensores").style.display = catRgb === "sensores" ? "grid" : "none";

        sec.querySelectorAll(".ally-rgb-modo-btn").forEach(btn => {
            const act = btn.dataset.modo === modoRgb;
            btn.style.background = act ? "#2a475e" : "#0e141b";
            btn.style.borderColor = act ? "#66c0f4" : "#3d5a73";
            btn.style.color = act ? "#66c0f4" : "#fff";
        });

        const usaColor = ["fijo", "respiracion"].includes(modoRgb);
        sec.querySelector("#ally-rgb-colores-box").style.display = usaColor ? "block" : "none";

        sec.querySelector("#ally-rgb-brillo-box").style.display = ["ciclo", "arcoiris"].includes(modoRgb) ? "none" : "block";



        const brilloVis = rgbOn ? Math.max(5, estado.rgb_brillo) : Math.max(5, estado.rgb_brillo_previo || 80);
        const brSl = sec.querySelector("#ally-rgb-brillo");
        const pctBr = ((brilloVis - 5) / 95) * 100;
        brSl.value = brilloVis;
        brSl.style.background = `linear-gradient(to right, #66c0f4 ${pctBr}%, #2a475e ${pctBr}%)`;
        sec.querySelector("#ally-rgb-brillo-val").textContent = `${brilloVis}%`;
        sec.querySelectorAll(".ally-brillo-tick").forEach((tk, idx) => {
            tk.style.background = ((idx + 1) * 5) <= brilloVis ? "#66c0f4" : "#4f6478";
        });

        const velAct = estado.rgb_vel || 2;
        const velSl = sec.querySelector("#ally-rgb-vel");
        const pctVel = ((velAct - 1) / 2) * 100;
        velSl.value = velAct;
        velSl.style.background = `linear-gradient(to right, #66c0f4 ${pctVel}%, #2a475e ${pctVel}%)`;
        velSl.style.setProperty("--vel-pct", `${pctVel}%`);
        sec.querySelector("#ally-rgb-vel-val").textContent = velAct === 1 ? t("slow") : (velAct === 3 ? t("fast") : t("medium"));


    }
    window.__allyActualizarEstado = (jsonStr) => {
        try {
            const nuevo = typeof jsonStr === "string" ? JSON.parse(jsonStr) : jsonStr;
            const editandoReciente = window.__allyUltimaEdicion && (Date.now() - window.__allyUltimaEdicion < 2500);
            if (editandoReciente) {
                estado.temp = nuevo.temp;
                estado.watts = nuevo.watts;
                estado.cpu_rpm = nuevo.cpu_rpm;
                estado.gpu_rpm = nuevo.gpu_rpm;
                estado.ac_conectado = nuevo.ac_conectado;
            } else {
                Object.assign(estado, nuevo);
            }
            actualizarUI();
        } catch (e) {}
    };

    if (window.__allyTelTimer) clearInterval(window.__allyTelTimer);
    window.__allyTelTimer = setInterval(() => {
        if (document.getElementById("ally-center-qam-section")) {
            enviarComando({ cmd: "estado" });
        }
    }, 2000);

    function intentarMontarEnConfigRapida() {
        const wifiEl = Array.from(document.querySelectorAll("div, span, label")).find(el => {
            const txt = (el.textContent || "").trim();
            return ["Wi-Fi", "WLAN", "Modo avión", "Airplane Mode", "Modo Avião", "Mode avion", "Flugmodus", "機内モード", "飞行模式", "无线局域网"].includes(txt);
        });
        if (!wifiEl) return;

        let cont = wifiEl.parentElement;
        while (cont && cont.parentElement && cont.parentElement !== document.body) {
            const cTxt = cont.textContent || "";
            if (["ESCALA", "SCALE", "SKALIERUNG", "ÉCHELLE", "スケーリング", "缩放"].some(k => cTxt.includes(k)) || cont.children.length >= 4) {
                break;
            }
            cont = cont.parentElement;
        }
        if (!cont || cont === document.body) return;

        const destino = (cont.parentElement && cont.parentElement !== document.body) ? cont.parentElement : cont;
        if (destino.children.length < 2) return;

        let sec = document.getElementById("ally-center-qam-section");
        if (sec && sec.isConnected) {
            if (!sec.querySelector("#ally-rgb-circulo")) {
                sec.remove();
                sec = null;
            } else {
                // Si Steam re-renderizó controles debajo de nuestro panel, lo devuelve al final
                if (sec.parentElement !== destino || destino.lastElementChild !== sec) {
                    destino.appendChild(sec);
                }
                return;
            }
        }

        sec = crearSeccionAlly();
        destino.appendChild(sec);
        enviarComando({ cmd: "estado" });
    }


    if (window.__allyMountTimer) clearInterval(window.__allyMountTimer);
    window.__allyMountTimer = setInterval(intentarMontarEnConfigRapida, 400);

    window.__allyObs = new MutationObserver(intentarMontarEnConfigRapida);
    window.__allyObs.observe(document.documentElement, { childList: true, subtree: true });
    intentarMontarEnConfigRapida();
})();""".replace("__JS_STRINGS_I18N__", JS_STRINGS_I18N).replace("__LANG_UI__", LANG_UI)


async def manejar_target(ws_url):
    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            await ws.send(json.dumps({"id": 2, "method": "Runtime.addBinding", "params": {"name": "allyBridgeSend"}}))
            await ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": JS_INJECT}}))

            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("method") == "Runtime.bindingCalled" and msg.get("params", {}).get("name") == "allyBridgeSend":
                    payload = json.loads(msg["params"]["payload"])
                    cmd = payload.get("cmd")

                    if cmd == "estado":
                        st = leer_estado_str()
                        if st:
                            await ws.send(json.dumps({
                                "id": 10,
                                "method": "Runtime.evaluate",
                                "params": {"expression": f"window.__allyActualizarEstado && window.__allyActualizarEstado({json.dumps(st)})"}
                            }))
                    elif cmd == "perfil":
                        ejecutar_ally(list(("perfil", str(payload.get("val", 1)))))
                    elif cmd == "tdp":
                        ejecutar_ally(list(("tdp", str(payload.get("val", 17)), str(payload.get("boost_pico", 0)))))
                    elif cmd == "cpu_boost":
                        ejecutar_ally(list(("boost", str(payload.get("val", 0)))))
                    elif cmd == "bateria":
                        ejecutar_ally(list(("bateria", str(payload.get("val", 1)))))
                    elif cmd == "guardar_curva":
                        pts_csv = ",".join(str(int(x)) for x in payload.get("val", ()))
                        ejecutar_ally(list(("guardar_curva", pts_csv)))
                    elif cmd == "fan_auto":
                        ejecutar_ally(list(("auto",)))
                    elif cmd == "fan_ambos":
                        ejecutar_ally(list(("ambos", str(int(payload.get("val", 50))), "guardar")))
                    elif cmd == "fan_sep":
                        ejecutar_ally(list(("cpu_fan", str(int(payload.get("cpu", 50))))))
                        ejecutar_ally(list(("gpu_fan", str(int(payload.get("gpu", 50))))))
                    elif cmd == "rgb":
                        modo = str(payload.get("modo", "fijo"))
                        rgb_val = payload.get("rgb") or (0, 210, 255)
                        r, g, b = [str(int(c)) for c in rgb_val]
                        br = str(int(payload.get("brillo", 80)))
                        vel = str(int(payload.get("vel", 2)))
                        ejecutar_ally(list(("rgb", modo, r, g, b, br, "1", vel)))
                    elif cmd == "sync_modos":
                        ejecutar_ally(["sync_modos", str(payload.get("val", "1"))], modo="game")

    except Exception:
        pass



async def vigilar_perfil_activo(modo):
    """Intercepta cambios externos (PowerDevil, enchufar/desenchufar AC, etc.) en ambos modos y restaura la config del usuario."""
    ruta_spl = "/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl1_spl/current_value"
    ruta_acpi = "/sys/firmware/acpi/platform_profile"
    mapa_acpi = {0: "quiet", 1: "balanced", 2: "performance"}

    while True:
        await asyncio.sleep(1.5)
        try:
            if not os.path.exists("/etc/ally-center.json"):
                continue
            with open("/etc/ally-center.json", "r") as f:
                est = json.load(f)

            # Lee la configuración correspondiente (Sync ON vs Por Modo)
            if est.get("sync_modos", True):
                cfg = est
            else:
                cfg = est.get("perfiles_modo", {}).get(modo, {})

            necesita_restaurar = False

            # Caso A: TDP Manual activo
            if cfg.get("tdp_manual") and os.path.exists(ruta_spl):
                tdp_esperado = int(cfg.get("tdp", 15))
                with open(ruta_spl, "r") as f:
                    tdp_kernel = int(f.read().strip())
                if tdp_kernel != tdp_esperado:
                    necesita_restaurar = True

            # Caso B: Perfil fijo (Silencioso / Equilibrado / Turbo)
            elif not cfg.get("tdp_manual") and os.path.exists(ruta_acpi):
                perfil_esperado = mapa_acpi.get(int(cfg.get("perfil", 1)), "balanced")
                with open(ruta_acpi, "r") as f:
                    perfil_kernel = f.read().strip()
                if perfil_kernel != perfil_esperado:
                    necesita_restaurar = True

            if necesita_restaurar:
                await asyncio.to_thread(ejecutar_ally, ["aplicar_modo", modo], modo)

        except asyncio.CancelledError:
            break
        except Exception:
            pass


def leer_sensores_rgb(st_rgb):
    """Lee el valor actual del sensor según el modo RGB dinámico sin abrir procesos externos."""
    modo = st_rgb.get("rgb_modo")
    brillo = st_rgb.get("rgb_brillo", 80)
    if brillo <= 0 or modo not in ("temp", "bateria", "hora"):
        return None

    if modo == "hora":
        import datetime
        h = datetime.datetime.now().hour
        franja = "manana" if 6 <= h < 12 else ("tarde" if 12 <= h < 19 else ("noche" if 19 <= h < 23 else "madrugada"))
        return ("hora", franja, brillo)

    if modo == "bateria":
        try:
            with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
                bat = int(f.read().strip())
            return ("bateria", bat, brillo)
        except Exception:
            return None

    if modo == "temp":
        try:
            for hw in os.listdir("/sys/class/hwmon"):
                name_path = f"/sys/class/hwmon/{hw}/name"
                temp_path = f"/sys/class/hwmon/{hw}/temp1_input"
                if os.path.exists(name_path) and os.path.exists(temp_path):
                    with open(name_path, "r") as fn:
                        if fn.read().strip() in ("k10temp", "amdgpu"):
                            with open(temp_path, "r") as ft:
                                temp_c = int(ft.read().strip()) // 1000
                            return ("temp", temp_c, brillo)
        except Exception:
            return None
    return None



async def bucle_principal():
    tareas_activas = {}
    entorno_anterior = None
    gamescope_anterior = None
    tarea_vigilante = None
    ultimo_estado_rgb = None  # Guarda (modo, valor_disparado, brillo)

    while True:
        try:
            targets = await asyncio.to_thread(obtener_targets)
            urls_actuales = set()
            for t in targets:
                title = t.get("title", "")
                url = t.get("webSocketDebuggerUrl", "")
                if url and "QuickAccess" in title:
                    urls_actuales.add(url)
                    if url not in tareas_activas:
                        tareas_activas.update({url: asyncio.create_task(manejar_target(url))})

            # Detecta si estamos en sesión de escritorio KDE Plasma
            en_sesion_kde = os.environ.get("XDG_CURRENT_DESKTOP", "").upper() == "KDE"
            gamescope_actual = False
            if not en_sesion_kde:
                for p in os.listdir("/proc"):
                    if p.isdigit():
                        try:
                            with open(f"/proc/{p}/comm", "r") as f:
                                if f.read().strip() == "gamescope":
                                    gamescope_actual = True
                                    break
                        except Exception:
                            pass

            entorno_actual = "game" if (urls_actuales or gamescope_actual) else "desktop"


            # Se dispara si cambió el entorno O si acaba de cerrarse la sesión de gamescope
            if entorno_actual != entorno_anterior or (gamescope_anterior is True and not gamescope_actual):
                entorno_anterior = entorno_actual
                gamescope_anterior = gamescope_actual

                if tarea_vigilante and not tarea_vigilante.done():
                    tarea_vigilante.cancel()

                if entorno_actual == "desktop":
                    await asyncio.sleep(1.0)
                await asyncio.to_thread(ejecutar_ally, ["aplicar_modo", entorno_actual], entorno_actual)
                tarea_vigilante = asyncio.create_task(vigilar_perfil_activo(entorno_actual))
            else:
                gamescope_anterior = gamescope_actual


            for url in list(tareas_activas.keys()):
                if url not in urls_actuales or tareas_activas.get(url).done():
                    tareas_activas.pop(url, None)

        except Exception as e:
            print(f"[ALLY-BRIDGE ERROR] {e}", flush=True)


        try:
            if os.path.exists("/etc/ally-center.json"):
                with open("/etc/ally-center.json", "r") as f:
                    st_rgb = json.load(f)
                lectura = leer_sensores_rgb(st_rgb)
                if lectura is not None:
                    modo_rgb, val_actual, brillo_rgb = lectura
                    debe_disparar = False
                    if ultimo_estado_rgb is None or ultimo_estado_rgb[0] != modo_rgb or ultimo_estado_rgb[2] != brillo_rgb:
                        debe_disparar = True
                    elif modo_rgb == "temp" and abs(val_actual - ultimo_estado_rgb[1]) >= 2:
                        debe_disparar = True
                    elif modo_rgb == "bateria" and abs(val_actual - ultimo_estado_rgb[1]) >= 3:
                        debe_disparar = True
                    elif modo_rgb == "hora" and val_actual != ultimo_estado_rgb[1]:
                        debe_disparar = True

                    if debe_disparar:
                        ultimo_estado_rgb = lectura
                        asyncio.create_task(asyncio.to_thread(ejecutar_ally, ["rgb_tick"]))
                else:
                    ultimo_estado_rgb = None
        except Exception:
            pass

        await asyncio.sleep(0.35 if entorno_actual == "game" else 1.0)




if __name__ == "__main__":
    try:
        cef_flag = os.path.expanduser("~/.local/share/Steam/.cef-enable-remote-debugging")
        if os.path.isdir(os.path.dirname(cef_flag)) and not os.path.exists(cef_flag):
            open(cef_flag, "a").close()
    except Exception:
        pass
    try:
        asyncio.run(bucle_principal())
    except KeyboardInterrupt:
        pass
