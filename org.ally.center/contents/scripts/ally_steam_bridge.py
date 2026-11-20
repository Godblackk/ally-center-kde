#!/usr/bin/env python3
import asyncio
import json
import subprocess
import urllib.request
import websockets
import os

SCRIPT_ALLY = os.path.expanduser("~/.local/share/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py")


def ejecutar_ally(args):
    cmd = ["sudo", "/usr/bin/python3", SCRIPT_ALLY] + args
    subprocess.run(cmd, capture_output=True, text=True)

def leer_estado_str():
    res = subprocess.run(["/usr/bin/python3", SCRIPT_ALLY, "estado"], capture_output=True, text=True)
    return res.stdout.strip() or "{}"

JS_INJECT = """
(() => {
    document.getElementById("ally-center-qam-section")?.remove();
    if (window.__allyObs) window.__allyObs.disconnect();

    const TEMPS = Array.from({length: 8}, (_, i) => (i + 3) * 10);
    let estado = { tdp: 25, boost: false, curva: Array.from({length: 8}, (_, i) => (i + 3) * 10), ac_conectado: true };

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

        const maxTdp = estado.ac_conectado ? 30 : 25;
        let html = `
            <div style="font-size: 12px; font-weight: 700; letter-spacing: 0.06em; color: #66c0f4; text-transform: uppercase; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                <span>⚡ Center ROG Ally X</span>
                <span style="font-size: 11px; color: #8b929a;">${estado.ac_conectado ? "AC" : "BAT"}</span>
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
            const clamped = Math.max(7, Math.min(maxTdp, nuevo));
            if (clamped !== estado.tdp) {
                estado.tdp = clamped;
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
        const existente = document.getElementById("ally-center-qam-section");
        if (existente && document.activeElement && !existente.contains(document.activeElement)) {
            existente.replaceWith(crearSeccionAlly());
        }
    }

    function intentarMontarEnRendimiento() {
        if (!document.body || document.getElementById("ally-center-qam-section")) return;

        const textos = Array.from(document.querySelectorAll("div, span, button")).filter(el => el.offsetParent !== null);
        const ancla = textos.find(el =>
            el.children.length === 0 &&
            /^(Utilizando perfil de rendimiento personalizado|Vista avanzada|Advanced View)$/i.test(el.textContent.trim())
        );

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
                        pts = [str(int(x)) for x in payload["val"]]
                        ejecutar_ally(["curva"] + pts)
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


