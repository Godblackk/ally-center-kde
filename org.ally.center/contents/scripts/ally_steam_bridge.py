#!/usr/bin/env python3
import asyncio
import json
import subprocess
import urllib.request
import websockets
import os

SCRIPT_ALLY = os.path.expanduser("~/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py")
SCRIPT_ESTADO = os.path.expanduser("~/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/estado.sh")


def ejecutar_ally(args):
    cmd = ["sudo", "/usr/bin/python3", SCRIPT_ALLY] + args
    subprocess.run(cmd, capture_output=True, text=True)

def leer_estado_str():
    res_sh = subprocess.run(["/bin/sh", SCRIPT_ESTADO], capture_output=True, text=True)
    datos = json.loads(res_sh.stdout.strip() or "{}")
    try:
        with open("/etc/ally-center.json", "r") as f:
            cfg = json.load(f)
            if "curva" in cfg:
                datos["curva"] = cfg["curva"]
    except Exception:
        pass
    return json.dumps(datos)

JS_INJECT = """
(() => {
    document.getElementById("ally-center-qam-section")?.remove();
    if (window.__allyObs) window.__allyObs.disconnect();

    const TEMPS = Array.from({length: 8}, (_, i) => (i + 3) * 10);
    let estado = {
        modelo: "Center ROG Ally X",
        tdp: 25, boost: false,
        curva: Array.from({length: 8}, (_, i) => (i + 3) * 10),
        ac_conectado: true,
        temp: "--", watts: "--", cpu_rpm: 0, gpu_rpm: 0
    };



    window.__allyRecibirEstado = (jsonStr) => {
        try {
            Object.assign(estado, JSON.parse(jsonStr));
            actualizarUI();
        } catch (e) {}
    };

    function enviarComando(obj) {
        if (window.allyBridgeSend) window.allyBridgeSend(JSON.stringify(obj));
    }

    function aplicarEstiloFoco(el) {
        el.setAttribute("tabindex", "0");
        el.style.outline = "none";
        el.style.borderRadius = "6px";
        el.style.padding = "4px 6px";
        el.style.transition = "background 0.15s, box-shadow 0.15s";
        el.addEventListener("focus", () => {
            el.style.background = "rgba(102, 192, 244, 0.18)";
            el.style.boxShadow = "0 0 0 2px #66c0f4";
            el.scrollIntoView({ block: "nearest", behavior: "smooth" });
        });
        el.addEventListener("blur", () => {
            el.style.background = "transparent";
            el.style.boxShadow = "none";
        });
    }

    function crearSeccionAlly() {
        const box = document.createElement("div");
        box.id = "ally-center-qam-section";
        box.style.cssText = "margin: 14px 0; padding: 12px; background: #171a21; border-radius: 8px; border: 1px solid rgba(102,192,244,0.45); color: #fff; font-family: sans-serif; box-sizing: border-box; position: relative; z-index: 10;";

        const getMaxTdp = () => estado.ac_conectado ? 30 : 25;
        const maxTdp = getMaxTdp();

        let html = `
            <div style="font-size: 12px; font-weight: 700; letter-spacing: 0.06em; color: #66c0f4; text-transform: uppercase; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                <span>⚡ <span id="ally-tel-modelo">${estado.modelo || "Center ROG Ally X"}</span></span>
                <span id="ally-tel-ac" style="font-size: 11px; color: #8b929a;">${estado.ac_conectado ? "AC" : "BAT"}</span>
            </div>


            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; background: rgba(0,0,0,0.28); padding: 8px; border-radius: 6px; margin-bottom: 12px; font-size: 11px;">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #8b929a;">APU</span>
                    <strong id="ally-tel-temp" style="color: #f5b041;">${estado.temp} °C</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #8b929a;">Consumo</span>
                    <strong id="ally-tel-watts" style="color: #58d68d;">${estado.watts} W</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #8b929a;">CPU Fan</span>
                    <strong id="ally-tel-cpu" style="color: #d6eaf8;">${estado.cpu_rpm} RPM</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #8b929a;">GPU Fan</span>
                    <strong id="ally-tel-gpu" style="color: #d6eaf8;">${estado.gpu_rpm} RPM</strong>
                </div>
            </div>

            <div id="ally-row-tdp" style="margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px;">
                    <span>Límite TDP</span>
                    <strong id="ally-tdp-val" style="color: #66c0f4; flex-shrink: 0;">${estado.tdp} W</strong>
                </div>
                <input id="ally-tdp-slider" type="range" min="7" max="${maxTdp}" value="${estado.tdp}" style="width: 100%; accent-color: #66c0f4; cursor: pointer;">
            </div>

            <div id="ally-row-boost" style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-bottom: 10px; border-top: 1px solid rgba(255,255,255,0.08); border-bottom: 1px solid rgba(255,255,255,0.08);">
                <span>CPU Boost</span>
                <span id="ally-boost-badge" style="background: ${estado.boost ? "#66c0f4" : "#2a475e"}; color: ${estado.boost ? "#0e141b" : "#fff"}; border-radius: 4px; padding: 3px 10px; font-weight: bold; font-size: 11px;">
                    ${estado.boost ? "ON" : "OFF"}
                </span>
            </div>

            <div style="font-size: 12px; font-weight: 600; color: #b8bcbf; margin-bottom: 6px;">Curva Ventiladores (8 Puntos)</div>
        `;

        TEMPS.forEach((t, i) => {
            const val = estado.curva[i] ?? 50;
            html += `
                <div class="ally-row-fan" data-idx="${i}" style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px; font-size: 12px;">
                    <span style="width: 36px; flex-shrink: 0; color: #8b929a;">${t}°C</span>
                    <input class="ally-pt" data-idx="${i}" type="range" min="0" max="100" step="5" value="${val}" style="flex: 1; min-width: 0; accent-color: #66c0f4; cursor: pointer;">
                    <span id="ally-pt-val-${i}" style="width: 36px; flex-shrink: 0; text-align: right; font-weight: 600;">${val}%</span>
                </div>
            `;
        });

        box.innerHTML = html;

        // Control TDP (táctil + cruceta)
        const rowTdp = box.querySelector("#ally-row-tdp");
        const tdpS = box.querySelector("#ally-tdp-slider");
        aplicarEstiloFoco(rowTdp);

        const setTdp = (nuevo) => {
            const maxActual = getMaxTdp();
            const clamped = Math.max(7, Math.min(maxActual, nuevo));
            if (clamped !== estado.tdp) {
            estado.tdp = clamped;
            tdpS.max = maxActual;
            tdpS.value = clamped;
            box.querySelector("#ally-tdp-val").textContent = clamped + " W";
            enviarComando({ cmd: "tdp", val: clamped });
            }
        };


        tdpS.oninput = (e) => {
            estado.tdp = parseInt(e.target.value);
            box.querySelector("#ally-tdp-val").textContent = estado.tdp + " W";
        };
        tdpS.onchange = () => enviarComando({ cmd: "tdp", val: estado.tdp });
        rowTdp.addEventListener("keydown", (e) => {
            if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); setTdp(estado.tdp - 1); }
            if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); setTdp(estado.tdp + 1); }
        });

        // Control CPU Boost (táctil + botón A / cruceta)
        const rowBoost = box.querySelector("#ally-row-boost");
        const badge = box.querySelector("#ally-boost-badge");
        aplicarEstiloFoco(rowBoost);

        const toggleBoost = () => {
            estado.boost = !estado.boost;
            badge.textContent = estado.boost ? "ON" : "OFF";
            badge.style.background = estado.boost ? "#66c0f4" : "#2a475e";
            badge.style.color = estado.boost ? "#0e141b" : "#fff";
            enviarComando({ cmd: "boost", val: estado.boost });
        };

        rowBoost.onclick = toggleBoost;
        rowBoost.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " " || e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                e.stopPropagation();
                toggleBoost();
            }
        });

        // Control Curva Ventiladores (táctil + cruceta)
        box.querySelectorAll(".ally-row-fan").forEach(row => {
            aplicarEstiloFoco(row);
            const idx = parseInt(row.dataset.idx);
            const slider = row.querySelector(".ally-pt");
            const valLabel = box.querySelector("#ally-pt-val-" + idx);

            const setFan = (nuevo) => {
                const clamped = Math.max(0, Math.min(100, nuevo));
                if (clamped !== estado.curva[idx]) {
                    estado.curva[idx] = clamped;
                    slider.value = clamped;
                    valLabel.textContent = clamped + "%";
                    enviarComando({ cmd: "curva", val: estado.curva });
                }
            };

            slider.oninput = (e) => {
                estado.curva[idx] = parseInt(e.target.value);
                valLabel.textContent = estado.curva[idx] + "%";
            };
            slider.onchange = () => enviarComando({ cmd: "curva", val: estado.curva });
            row.addEventListener("keydown", (e) => {
                if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); setFan((estado.curva[idx] ?? 50) - 5); }
                if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); setFan((estado.curva[idx] ?? 50) + 5); }
            });
        });

        return box;
    }

    function actualizarUI() {
        const sec = document.getElementById("ally-center-qam-section");
        if (!sec) return;

        // 1. Actualiza modelo, AC/BAT y telemetría en vivo sin reconstruir la tarjeta
        const elModelo = sec.querySelector("#ally-tel-modelo");
        const elAc = sec.querySelector("#ally-tel-ac");
        const elTemp = sec.querySelector("#ally-tel-temp");
        const elWatts = sec.querySelector("#ally-tel-watts");
        const elCpu = sec.querySelector("#ally-tel-cpu");
        const elGpu = sec.querySelector("#ally-tel-gpu");

        if (elModelo && estado.modelo) elModelo.textContent = estado.modelo;
        if (elAc) elAc.textContent = estado.ac_conectado ? "AC" : "BAT";
        if (elTemp) elTemp.textContent = `${estado.temp ?? "--"} °C`;
        if (elWatts) elWatts.textContent = `${estado.watts ?? "--"} W`;
        if (elCpu) elCpu.textContent = `${estado.cpu_rpm ?? 0} RPM`;
        if (elGpu) elGpu.textContent = `${estado.gpu_rpm ?? 0} RPM`;

        // 2. Actualiza el tope dinámico (25W BAT / 30W AC) y valor del slider sin perder el foco
        const tdpS = sec.querySelector("#ally-tdp-slider");
        const tdpVal = sec.querySelector("#ally-tdp-val");
        if (tdpS && tdpVal) {
            const maxActual = estado.ac_conectado ? 30 : 25;
            tdpS.max = maxActual;
            if (estado.tdp > maxActual) estado.tdp = maxActual;
            tdpS.value = estado.tdp;
            tdpVal.textContent = `${estado.tdp} W`;
        }

        // 3. Solo reconstruye el resto si el usuario no tiene el foco adentro
        if (document.activeElement && !sec.contains(document.activeElement)) {
            sec.replaceWith(crearSeccionAlly());
        }
    }



    function intentarMontarEnRendimiento() {
        if (!document.body || document.getElementById("ally-center-qam-section")) return;

        // 1. Busca primero por textos conocidos (ES / EN / PT / FR / DE / IT)
        const textos = Array.from(document.querySelectorAll("div, span, button")).filter(el => el.offsetParent !== null);
        let ancla = textos.find(el =>
            el.children.length === 0 &&
            /^(Utilizando perfil de rendimiento personalizado|Vista avanzada|Advanced View|Visualização avançada|Vue avancée|Erweiterte Ansicht|Vista avanzata)$/i.test(el.textContent.trim())
        );

        // 2. Respaldo universal independiente del idioma: detecta los sliders nativos de la pestaña Rendimiento
        if (!ancla) {
            const slidersVisibles = Array.from(document.querySelectorAll('input[type="range"], [role="slider"]'))
                .filter(el => el.offsetParent !== null && !el.closest("#ally-center-qam-section"));
            if (slidersVisibles.length >= 2) {
                ancla = slidersVisibles[slidersVisibles.length - 1];
            }
        }

        if (ancla) {
            let fila = ancla;
            while (fila.parentElement && fila.parentElement !== document.body) {
                if (fila.parentElement.children.length >= 4) {
                    fila.insertAdjacentElement("afterend", crearSeccionAlly());
                    enviarComando({ cmd: "estado" });
                    return;
                }
                fila = fila.parentElement;
            }
        }
    }

    if (window.__allyTelTimer) clearInterval(window.__allyTelTimer);
    window.__allyTelTimer = setInterval(() => {
        const sec = document.getElementById("ally-center-qam-section");
        if (sec && sec.offsetParent !== null) {
            enviarComando({ cmd: "estado" });
        }
    }, 1500);


    window.__allyObs = new MutationObserver(() => intentarMontarEnRendimiento());
    window.__allyObs.observe(document.documentElement, { childList: true, subtree: true });
    intentarMontarEnRendimiento();
})();
"""

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
                        est = leer_estado_str()
                        await ws.send(json.dumps({
                            "id": 10,
                            "method": "Runtime.evaluate",
                            "params": {"expression": f"window.__allyRecibirEstado({json.dumps(est)})"}
                        }))
                    elif cmd == "tdp":
                        ejecutar_ally(["tdp", str(int(payload["val"]))])
                    elif cmd == "boost":
                        ejecutar_ally(["boost", "1" if payload["val"] else "0"])
                    elif cmd == "curva":
                        pts_csv = ",".join(str(int(x)) for x in payload["val"])
                        ejecutar_ally(["guardar_curva", pts_csv])

    except Exception:
        pass


async def bucle_principal():
    tareas = {}
    while True:
        try:
            with urllib.request.urlopen("http://localhost:8080/json", timeout=2) as resp:
                targets = json.loads(resp.read().decode())
            for t in targets:
                title = t.get("title", "")
                if t.get("type") == "page" and title.startswith("QuickAccess"):
                    tid = t.get("id")
                    ws_url = t.get("webSocketDebuggerUrl")
                    if tid and ws_url and (tid not in tareas or tareas[tid].done()):
                        tareas[tid] = asyncio.create_task(manejar_target(ws_url))
        except Exception:
            pass
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(bucle_principal())


