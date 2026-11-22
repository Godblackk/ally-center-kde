#!/usr/bin/env python3
import asyncio
import json
import os
import subprocess
import urllib.request
import websockets
import struct
import glob


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
            if "tdp_manual" in cfg:
                datos["tdp_manual"] = cfg["tdp_manual"]
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
        perfil: 1,
        tdp_manual: false,
        tdp: 25,
        boost: false,
        curva: Array.from({length: 8}, (_, i) => (i + 3) * 10),
        ac_conectado: true,
        temp: "--",
        watts: "--",
        cpu_rpm: 0,
        gpu_rpm: 0
    };

    let bloqueoSyncHasta = 0;
    let ultimoPerfilKernel = null;

    window.__allyRecibirEstado = (jsonStr) => {
        if (Date.now() < bloqueoSyncHasta) return;
        try {
            const nuevo = JSON.parse(jsonStr);
            const cambioExternoPerfil = (
                typeof nuevo.perfil === "number" && (
                    (ultimoPerfilKernel !== null && nuevo.perfil !== ultimoPerfilKernel) ||
                    (nuevo.tdp_manual === true && nuevo.perfil !== 2)
                )
            );
            if (typeof nuevo.perfil === "number") ultimoPerfilKernel = nuevo.perfil;

            if (typeof nuevo.tdp === "number" && nuevo.tdp >= 7) estado.tdp = nuevo.tdp;
            Object.assign(estado, nuevo);

            if (cambioExternoPerfil) {
                estado.tdp_manual = false;
                estado.tdp_boost = false;
                enviarComando({ cmd: "perfil", val: estado.perfil });
            }
            if (!estado.tdp_manual) {
                estado.tdp = (estado.perfil === 0) ? 13 : (estado.perfil === 1 ? 17 : (estado.ac_conectado ? 30 : 25));
            }
            actualizarUI();
        } catch (e) {}
    };

    function pausarSyncSteam() { bloqueoSyncHasta = Date.now() + 2500; }

    function enviarComando(obj) {
        if (obj && obj.cmd !== "estado") pausarSyncSteam();
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
        box.style.cssText = "margin: 14px 10px; padding: 12px; background: #171a21; border-radius: 8px; border: 1px solid rgba(102,192,244,0.45); color: #fff; font-family: sans-serif; box-sizing: border-box; position: relative; z-index: 10;";
        const getMaxTdp = () => estado.ac_conectado ? 30 : 25;
        const maxTdp = getMaxTdp();
        const perfMax = estado.ac_conectado ? "30W" : "25W";
        const nombresPerfil = { 0: "Ahorro (13W)", 1: "Equilibrado (17W)", 2: `Rendimiento (${perfMax})` };
        const textoPerfil = nombresPerfil[estado.perfil] ?? "Equilibrado (17W)";
        const manualActivo = Boolean(estado.tdp_manual);

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

                <div id="ally-perfil-wrapper" style="position: relative; margin-bottom: 10px; opacity: ${manualActivo ? "0.4" : "1"}; pointer-events: ${manualActivo ? "none" : "auto"}; transition: opacity 0.15s;">
                <div id="ally-row-perfil" style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; cursor: pointer;">
                    <span>Perfil Energía</span>
                    <span id="ally-perfil-badge" style="background: #2a475e; border: 1px solid #66c0f4; color: #fff; border-radius: 4px; padding: 4px 10px; font-weight: 600; font-size: 12px;">
                        ${textoPerfil} ▾
                    </span>
                </div>
            <div id="ally-perfil-menu" style="display: none; flex-direction: column; gap: 4px; margin-top: 6px; background: #171a21; border: 1px solid rgba(102, 192, 244, 0.35); border-radius: 6px; padding: 6px;">
                 <div class="ally-perfil-opt" data-val="0" style="padding: 6px 10px; border-radius: 4px; font-size: 12px; cursor: pointer;">Ahorro (13W)</div>
                 <div class="ally-perfil-opt" data-val="1" style="padding: 6px 10px; border-radius: 4px; font-size: 12px; cursor: pointer;">Equilibrado (17W)</div>
                 <div class="ally-perfil-opt" data-val="2" style="padding: 6px 10px; border-radius: 4px; font-size: 12px; cursor: pointer;">Rendimiento (${perfMax})</div>
            </div>

            </div>


            <div id="ally-row-manual-toggle" style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-bottom: 8px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; cursor: pointer;">
                <span>Límite TDP Manual</span>
                <span id="ally-manual-badge" style="background: ${manualActivo ? "#66c0f4" : "#2a475e"}; color: ${manualActivo ? "#0e141b" : "#fff"}; border-radius: 4px; padding: 3px 10px; font-weight: bold; font-size: 11px;">
                    ${manualActivo ? "ON" : "OFF"}
                </span>
            </div>

            <div id="ally-manual-box" style="opacity: ${manualActivo ? "1" : "0.4"}; pointer-events: ${manualActivo ? "auto" : "none"}; margin-bottom: 10px; transition: opacity 0.15s;">
                <div id="ally-row-tdp" style="margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px;">
                        <span>Límite TDP</span>
                        <strong id="ally-tdp-val" style="color: #66c0f4; flex-shrink: 0;">${estado.tdp} W</strong>
                    </div>
                    <input id="ally-tdp-slider" type="range" min="7" max="${maxTdp}" value="${estado.tdp}" style="width: 100%; accent-color: #66c0f4; cursor: pointer;">
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; width: 100%; box-sizing: border-box;">
                 <div class="ally-preset-btn" data-w="13" style="background:#1b2838; color:#fff; border:1px solid rgba(255,255,255,0.15); border-radius:4px; padding:5px 0; font-size:12px; font-weight:600; text-align:center; cursor:pointer; box-sizing:border-box;">13W</div>
                 <div class="ally-preset-btn" data-w="17" style="background:#1b2838; color:#fff; border:1px solid rgba(255,255,255,0.15); border-radius:4px; padding:5px 0; font-size:12px; font-weight:600; text-align:center; cursor:pointer; box-sizing:border-box;">17W</div>
                 <div class="ally-preset-btn" data-w="25" style="background:#1b2838; color:#fff; border:1px solid rgba(255,255,255,0.15); border-radius:4px; padding:5px 0; font-size:12px; font-weight:600; text-align:center; cursor:pointer; box-sizing:border-box;">25W</div>
                 <div id="ally-preset-30" class="ally-preset-btn" data-w="30" style="background:#1b2838; color:#fff; border:1px solid rgba(255,255,255,0.15); border-radius:4px; padding:5px 0; font-size:12px; font-weight:600; text-align:center; cursor:pointer; box-sizing:border-box; display:${estado.ac_conectado ? "block" : "none"};">30W</div>
            </div>

                <div id="ally-row-tdp-boost" style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding: 6px 8px; border-radius: 6px; background: rgba(255,255,255,0.04); cursor: pointer;">
                    <span style="font-size: 12px; color: #dcdedf;">Boost Pico (SPPT / FPPT)</span>
                    <span id="ally-tdp-boost-badge" style="background: #2a475e; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600;">OFF</span>
                </div>
            </div>

            <div id="ally-row-boost" style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-bottom: 10px; border-top: 1px solid rgba(255,255,255,0.08); border-bottom: 1px solid rgba(255,255,255,0.08); cursor: pointer;">
                <span>CPU Boost</span>
                <span id="ally-boost-badge" style="background: ${estado.boost ? "#66c0f4" : "#2a475e"}; color: ${estado.boost ? "#0e141b" : "#fff"}; border-radius: 4px; padding: 3px 10px; font-weight: bold; font-size: 11px;">
                    ${estado.boost ? "ON" : "OFF"}
                </span>
            </div>

            <div style="border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px; background: rgba(0,0,0,0.18); margin-top: 4px;">
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: 600; color: #b8bcbf; margin-bottom: 8px;">
                    <span>Curva Ventiladores</span>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span id="ally-btn-curva-reset" title="Restaurar curva base" style="background: #1b2838; color: #dcdedf; border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; padding: 2px 7px; font-size: 12px; cursor: pointer;">↺</span>
                        <span id="ally-row-curva-modo" style="background: #2a475e; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 11px; cursor: pointer;">Cascada</span>
                    </div>
                </div>
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
        html += `</div>`;


        box.innerHTML = html;

        const rowPerfil = box.querySelector("#ally-row-perfil");
        const perfilBadge = box.querySelector("#ally-perfil-badge");
        const perfilMenu = box.querySelector("#ally-perfil-menu");
        aplicarEstiloFoco(rowPerfil);

        if (manualActivo) rowPerfil.tabIndex = -1;

        const seleccionarPerfil = (nuevo) => {
            estado.perfil = nuevo;
            ultimoPerfilKernel = nuevo;
            estado.tdp_manual = false;
            estado.tdp_boost = false;
            estado.tdp = (nuevo === 0) ? 13 : (nuevo === 1 ? 17 : (estado.ac_conectado ? 30 : 25));
            const pMax = estado.ac_conectado ? "30W" : "25W";
            const nombres = { 0: "Ahorro (13W)", 1: "Equilibrado (17W)", 2: `Rendimiento (${pMax})` };
            perfilBadge.textContent = nombres[nuevo] + " ▾";
            perfilMenu.style.display = "none";
            actualizarEstadoManual(false);
            actualizarUI();
            enviarComando({ cmd: "perfil", val: nuevo });
            rowPerfil.focus();
        };


        const toggleMenuPerfil = () => {
            const abierto = perfilMenu.style.display === "flex";
            perfilMenu.style.display = abierto ? "none" : "flex";
            if (!abierto) {
                const actualOpt = perfilMenu.querySelector(`.ally-perfil-opt[data-val="${estado.perfil ?? 1}"]`) || perfilMenu.firstElementChild;
                actualOpt?.focus();
            }
        };

        rowPerfil.onclick = toggleMenuPerfil;
        rowPerfil.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); toggleMenuPerfil(); }
        });

        perfilMenu.querySelectorAll(".ally-perfil-opt").forEach(opt => {
            aplicarEstiloFoco(opt);
            const val = parseInt(opt.dataset.val);
            opt.onclick = () => seleccionarPerfil(val);
            opt.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); seleccionarPerfil(val); }
                if (e.key === "Escape" || e.key === "Backspace") { e.preventDefault(); e.stopPropagation(); perfilMenu.style.display = "none"; rowPerfil.focus(); }
            });
        });

        const rowManual = box.querySelector("#ally-row-manual-toggle");
        const manualBadge = box.querySelector("#ally-manual-badge");
        const manualBox = box.querySelector("#ally-manual-box");
        aplicarEstiloFoco(rowManual);


        function actualizarEstadoManual(activo) {
            estado.tdp_manual = activo;
            manualBadge.textContent = activo ? "ON" : "OFF";
            manualBadge.style.background = activo ? "#66c0f4" : "#2a475e";
            manualBadge.style.color = activo ? "#0e141b" : "#fff";
            manualBox.style.opacity = activo ? "1" : "0.4";
            manualBox.style.pointerEvents = activo ? "auto" : "none";

            const pWrap = box.querySelector("#ally-perfil-wrapper");
            if (pWrap) {
                pWrap.style.opacity = activo ? "0.4" : "1";
                pWrap.style.pointerEvents = activo ? "none" : "auto";
            }

            rowPerfil.tabIndex = activo ? -1 : 0;
            rowTdp.tabIndex = activo ? 0 : -1;
            box.querySelectorAll(".ally-preset-btn").forEach(b => b.tabIndex = activo ? 0 : -1);


            if (activo && perfilMenu) perfilMenu.style.display = "none";

            if (activo) {
                enviarComando({ cmd: "tdp", val: estado.tdp });
            } else {
                enviarComando({ cmd: "perfil", val: estado.perfil ?? 1 });
            }

            actualizarUI();
        }

        rowManual.onclick = () => actualizarEstadoManual(!estado.tdp_manual);
        rowManual.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " " || e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                e.stopPropagation();
                actualizarEstadoManual(!estado.tdp_manual);
            }
        });

        const rowTdp = box.querySelector("#ally-row-tdp");
        const tdpS = box.querySelector("#ally-tdp-slider");
        aplicarEstiloFoco(rowTdp);
               const setTdp = (n) => {
            const c = Math.max(7, Math.min(getMaxTdp(), n));
            estado.tdp = c;
            if (estado.tdp < 25) estado.tdp_boost = false;
            tdpS.max = getMaxTdp();
            tdpS.value = c;
            box.querySelector("#ally-tdp-val").textContent = c + " W";
            actualizarUI();
            enviarComando({ cmd: "tdp", val: c, boost_pico: estado.tdp_boost ? 1 : 0 });
        };


        let tdpDebounce = null;
        tdpS.oninput = (e) => {
            const v = parseInt(e.target.value);
            estado.tdp = v;
            if (estado.tdp < 25) estado.tdp_boost = false;
            box.querySelector("#ally-tdp-val").textContent = v + " W";
            actualizarUI();
            clearTimeout(tdpDebounce);
            tdpDebounce = setTimeout(() => setTdp(v), 180);
        };
        tdpS.onchange = () => setTdp(parseInt(tdpS.value));
        rowTdp.addEventListener("keydown", (e) => {
            if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); setTdp(estado.tdp - 1); }
            if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); setTdp(estado.tdp + 1); }
        });

        box.querySelectorAll(".ally-preset-btn").forEach(btn => {
            aplicarEstiloFoco(btn);
            const aplicarPreset = () => {
                if (!estado.tdp_manual) actualizarEstadoManual(true);
                setTdp(parseInt(btn.dataset.w));
            };
            btn.onpointerdown = (e) => { e.preventDefault(); e.stopPropagation(); aplicarPreset(); };
            btn.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); aplicarPreset(); }
            });
        });

        const rowTdpBoost = box.querySelector("#ally-row-tdp-boost");
        if (rowTdpBoost) {
            aplicarEstiloFoco(rowTdpBoost);
            const toggleTdpBoost = (e) => {
                if (e) { e.preventDefault(); e.stopPropagation(); }
                if (!estado.tdp_manual || estado.tdp < 25) return;
                estado.tdp_boost = !estado.tdp_boost;
                actualizarUI();
                enviarComando({ cmd: "tdp", val: estado.tdp, boost_pico: estado.tdp_boost ? 1 : 0 });
            };
            rowTdpBoost.onpointerdown = toggleTdpBoost;
            rowTdpBoost.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") toggleTdpBoost(e);
            });
        }

        if (!manualActivo) {
            rowTdp.tabIndex = -1;
            if (rowTdpBoost) rowTdpBoost.tabIndex = -1;
            box.querySelectorAll(".ally-preset-btn").forEach(b => b.tabIndex = -1);
        }




        let curvaTodosJuntos = false;
        const rowCurvaModo = box.querySelector("#ally-row-curva-modo");
        aplicarEstiloFoco(rowCurvaModo);
        const toggleCurvaModo = (e) => {
            if (e) { e.preventDefault(); e.stopPropagation(); }
            curvaTodosJuntos = !curvaTodosJuntos;
            rowCurvaModo.textContent = curvaTodosJuntos ? "Todos juntos" : "Cascada";
            rowCurvaModo.style.background = curvaTodosJuntos ? "#66c0f4" : "#2a475e";
            rowCurvaModo.style.color = curvaTodosJuntos ? "#0e141b" : "#fff";
        };
        rowCurvaModo.onpointerdown = toggleCurvaModo;
        rowCurvaModo.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " " || e.key === "ArrowLeft" || e.key === "ArrowRight") toggleCurvaModo(e);
        });

        const btnCurvaReset = box.querySelector("#ally-btn-curva-reset");
        if (btnCurvaReset) {
            aplicarEstiloFoco(btnCurvaReset);
            const resetCurvaBase = (e) => {
                if (e) { e.preventDefault(); e.stopPropagation(); }
                estado.curva = new Array(15, 25, 40, 55, 70, 85, 95, 100);
                estado.curva.forEach((v, j) => {
                    const s = box.querySelector(`.ally-pt[data-idx="${j}"]`);
                    const l = box.querySelector(`#ally-pt-val-${j}`);
                    if (s) s.value = v;
                    if (l) l.textContent = v + "%";
                });
                enviarComando({ cmd: "curva", val: estado.curva });
            };
            btnCurvaReset.onpointerdown = resetCurvaBase;
            btnCurvaReset.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") resetCurvaBase(e);
            });
        }
        box.querySelectorAll(".ally-row-fan").forEach(row => {
            aplicarEstiloFoco(row);
            const idx = parseInt(row.dataset.idx);
            const slider = row.querySelector(".ally-pt");
            let fanDebounce = null;

            const setFan = (nuevo) => {
                const val = Math.max(0, Math.min(100, Math.round(nuevo / 5) * 5));
                if (curvaTodosJuntos) {
                    estado.curva = Array(8).fill(val);
                } else {
                    estado.curva[idx] = val;
                    for (let j = idx + 1; j < 8; j++) if (estado.curva[j] < val) estado.curva[j] = val;
                    for (let j = idx - 1; j >= 0; j--) if (estado.curva[j] > val) estado.curva[j] = val;
                }
                estado.curva.forEach((v, j) => {
                    const s = box.querySelector(`.ally-pt[data-idx="${j}"]`);
                    const l = box.querySelector(`#ally-pt-val-${j}`);
                    if (s) s.value = v;
                    if (l) l.textContent = v + "%";
                });
                clearTimeout(fanDebounce);
                fanDebounce = setTimeout(() => enviarComando({ cmd: "curva", val: estado.curva }), 180);
            };

            slider.oninput = (e) => setFan(parseInt(e.target.value));
            row.addEventListener("keydown", (e) => {
                if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); setFan(estado.curva[idx] - 5); }
                if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); setFan(estado.curva[idx] + 5); }
            });
        });

        return box;
    }

    function actualizarUI() {
        const sec = document.getElementById("ally-center-qam-section");
        if (!sec) return;

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

        const perfilBadge = sec.querySelector("#ally-perfil-badge");
        if (perfilBadge) {
            const pMax = estado.ac_conectado ? "30W" : "25W";
            const nombres = { 0: "Ahorro (13W)", 1: "Equilibrado (17W)", 2: `Rendimiento (${pMax})` };
            perfilBadge.textContent = (nombres[estado.perfil] ?? "Equilibrado (17W)") + " ▾";
        }

        const preset30 = sec.querySelector("#ally-preset-30");
        if (preset30) preset30.style.display = estado.ac_conectado ? "block" : "none";
        const tdpS = sec.querySelector("#ally-tdp-slider");
        const tdpVal = sec.querySelector("#ally-tdp-val");
        if (tdpS && tdpVal) {
            const maxActual = estado.ac_conectado ? 30 : 25;
            tdpS.max = maxActual;
            if (estado.tdp > maxActual) estado.tdp = maxActual;
            tdpS.value = estado.tdp;
            tdpVal.textContent = `${estado.tdp} W`;
        }
        const manualOn = Boolean(estado.tdp_manual);
        const mBadge = sec.querySelector("#ally-manual-badge");
        const mBox = sec.querySelector("#ally-manual-box");
        const pWrap = sec.querySelector("#ally-perfil-wrapper");
        if (mBadge) {
            mBadge.textContent = manualOn ? "ON" : "OFF";
            mBadge.style.background = manualOn ? "#66c0f4" : "#2a475e";
            mBadge.style.color = manualOn ? "#0e141b" : "#fff";
        }
        if (mBox) {
            mBox.style.opacity = manualOn ? "1" : "0.4";
            mBox.style.pointerEvents = manualOn ? "auto" : "none";
        }
        if (pWrap) {
            pWrap.style.opacity = manualOn ? "0.4" : "1";
            pWrap.style.pointerEvents = manualOn ? "none" : "auto";
        }
        const bBadge = sec.querySelector("#ally-boost-badge");
        if (bBadge) {
            bBadge.textContent = estado.boost ? "ON" : "OFF";
            bBadge.style.background = estado.boost ? "#66c0f4" : "#2a475e";
            bBadge.style.color = estado.boost ? "#0e141b" : "#fff";
        }
        const tbRow = sec.querySelector("#ally-row-tdp-boost");
        const tbBadge = sec.querySelector("#ally-tdp-boost-badge");
        const tbHabilitado = manualOn && estado.tdp >= 25;
        const tbActivo = tbHabilitado && Boolean(estado.tdp_boost);
        if (tbRow) {
            tbRow.style.opacity = tbHabilitado ? "1" : "0.4";
            tbRow.style.pointerEvents = tbHabilitado ? "auto" : "none";
            tbRow.tabIndex = tbHabilitado ? 0 : -1;
        }
        if (tbBadge) {
            tbBadge.textContent = tbActivo ? "ON" : "OFF";
            tbBadge.style.background = tbActivo ? "#66c0f4" : "#2a475e";
            tbBadge.style.color = tbActivo ? "#0e141b" : "#fff";
        }
        if (Array.isArray(estado.curva)) {
            estado.curva.forEach((v, idx) => {
                const sl = sec.querySelector(`.ally-pt[data-idx="${idx}"]`);
                const lb = sec.querySelector(`#ally-pt-val-${idx}`);
                if (sl && document.activeElement !== sl) sl.value = v;
                if (lb) lb.textContent = `${v}%`;
            });
        }
    }

    function intentarMontarEnRendimiento() {

        if (!document.body) return;

        const textos = Array.from(document.querySelectorAll("div, span, button")).filter(el => el.offsetParent !== null);
        const enPestanaRendimiento = textos.some(el =>
            el.children.length === 0 &&
            /^(RENDIMIENTO|PERFORMANCE|DESEMPENHO|PRESTAZIONI|LEISTUNG)$/i.test(el.textContent.trim())
        );

        const existente = document.getElementById("ally-center-qam-section");
        if (!enPestanaRendimiento) {
            if (existente) existente.remove();
            return;
        }
        if (existente && existente.isConnected) return;

        let ancla = textos.find(el =>
            el.children.length === 0 &&
            /^(Utilizando perfil de rendimiento personalizado|Vista avanzada|Advanced View|Visualização avançada|Vue avancée|Erweiterte Ansicht|Vista avanzata)$/i.test(el.textContent.trim())
        );

        if (!ancla) {
            const slidersVisibles = Array.from(document.querySelectorAll('input[type="range"], [role="slider"]'))
                .filter(el => el.offsetParent !== null && !el.closest("#ally-center-qam-section"));
            if (slidersVisibles.length >= 1) {
                ancla = slidersVisibles[slidersVisibles.length - 1];
            }
        }

        if (ancla) {
            let contenedorScroll = ancla.parentElement;
            let ultimoScroll = null;
            while (contenedorScroll && contenedorScroll !== document.body) {
                const st = window.getComputedStyle(contenedorScroll);
                if (st.overflowY === "auto" || st.overflowY === "scroll") {
                    ultimoScroll = contenedorScroll;
                }
                contenedorScroll = contenedorScroll.parentElement;
            }
            if (ultimoScroll) {
                const box = crearSeccionAlly();
                ultimoScroll.appendChild(box);
                enviarComando({ cmd: "estado" });
            }
        }

    }

    if (window.__allyMountTimer) clearInterval(window.__allyMountTimer);
    window.__allyMountTimer = setInterval(() => {
        intentarMontarEnRendimiento();
    }, 250);

    if (window.__allyTelTimer) clearInterval(window.__allyTelTimer);
    window.__allyTelTimer = setInterval(() => {
        const sec = document.getElementById("ally-center-qam-section");
        if (sec && sec.isConnected) {
            enviarComando({ cmd: "estado" });
        }
    }, 1500);


    //SECCION DE CONTROLES PARA VENTANA CREADA
    let allyNavIdx = -1;
    function getAllyNavItems() {
        const sec = document.getElementById("ally-center-qam-section");
        if (!sec || sec.offsetParent === null) return [];
        return Array.from(sec.querySelectorAll('[tabindex="0"]')).filter(el => el.offsetParent !== null);
    }

    function pintarFocoAlly(idx) {
        const items = getAllyNavItems();
        items.forEach((el, i) => {
            if (i === idx) {
                el.style.outline = "2px solid #66c0f4";
                el.style.outlineOffset = "2px";
                el.style.background = "rgba(102, 192, 244, 0.22)";
                el.scrollIntoView({ block: "nearest", behavior: "smooth" });
                el.focus({ preventScroll: true });
            } else {
                el.style.outline = "none";
                el.style.background = el.classList.contains("ally-preset-btn") ? "#1b2838" : "transparent";
            }
        });
        allyNavIdx = idx;
    }

    window.__allyControllerBtn = (btn) => {
        const sec = document.getElementById("ally-center-qam-section");
        if (!sec || sec.offsetParent === null) {
            if (allyNavIdx !== -1) pintarFocoAlly(-1);
            return;
        }
        const items = getAllyNavItems();
        if (!items.length) return;

        // Si aún estamos arriba en Steam y el foco blanco (.gpfocus) está en "Vista avanzada" + pulsamos Abajo
        if (allyNavIdx === -1) {
            const scroll = sec.parentElement;
            const enFondo = scroll ? (scroll.scrollTop + scroll.clientHeight >= scroll.scrollHeight - 60) : false;
            if (btn === "Y" || (btn === "DOWN" && enFondo)) {
                pintarFocoAlly(0);
            }
            return;
        }


        const actual = items[allyNavIdx];
        if (!actual) { pintarFocoAlly(-1); return; }

        if (btn === "DOWN") {
            pintarFocoAlly(Math.min(items.length - 1, allyNavIdx + 1));
        } else if (btn === "UP") {
            if (allyNavIdx <= 0) {
                pintarFocoAlly(-1);
                document.querySelector(".gpfocus")?.focus();
            } else {
                pintarFocoAlly(allyNavIdx - 1);
            }
        } else if (btn === "LEFT" || btn === "RIGHT") {
            const key = btn === "LEFT" ? "ArrowLeft" : "ArrowRight";
            actual.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
        } else if (btn === "A") {
            actual.click();
            setTimeout(() => {
                const nuevos = getAllyNavItems();
                if (allyNavIdx >= nuevos.length) pintarFocoAlly(nuevos.length - 1);
            }, 50);
        } else if (btn === "B") {
            const menu = document.getElementById("ally-perfil-menu");
            if (menu && menu.style.display === "flex") {
                menu.style.display = "none";
                pintarFocoAlly(0);
            } else {
                pintarFocoAlly(-1);
                document.querySelector(".gpfocus")?.focus();
            }
        }
    };


    window.__allyObs = new MutationObserver(() => intentarMontarEnRendimiento());
    window.__allyObs.observe(document.documentElement, { childList: true, subtree: true });
    intentarMontarEnRendimiento();





})();
"""

JS_SHARED_INPUT = r"""
(() => {
    if (window.__allySharedInputHooked) return;
    window.__allySharedInputHooked = true;
    const mapBtn = {
        1: "UP", 32: "UP",
        4: "DOWN", 35: "DOWN",
        3: "LEFT", 34: "LEFT",
        2: "RIGHT", 33: "RIGHT",
        5: "A",
        6: "B"
    };
    let lastTs = 0;
    if (window.SteamClient && SteamClient.Input && SteamClient.Input.RegisterForControllerInputMessages) {
        SteamClient.Input.RegisterForControllerInputMessages((_ctrlIdx, btnCode, pressed) => {
            if (!pressed) return;
            const accion = mapBtn[btnCode];
            if (!accion) return;
            const now = Date.now();
            if (now - lastTs < 120) return;
            lastTs = now;
            if (window.allySharedSend) window.allySharedSend(accion);
        });
    }
})();
"""



qam_ws_activo = None
async def manejar_shared(ws_url):
    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            await ws.send(json.dumps({"id": 2, "method": "Runtime.addBinding", "params": {"name": "allySharedSend"}}))
            await ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": JS_SHARED_INPUT}}))
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("method") == "Runtime.bindingCalled" and msg.get("params", {}).get("name") == "allySharedSend":
                    accion = msg["params"]["payload"]
                    if qam_ws_activo:
                        try:
                            await qam_ws_activo.send(json.dumps({
                                "id": 50,
                                "method": "Runtime.evaluate",
                                "params": {"expression": f"window.__allyControllerBtn && window.__allyControllerBtn({json.dumps(accion)})"}
                            }))
                        except Exception:
                            pass
    except Exception:
        pass


async def manejar_target(ws_url):
    global qam_ws_activo
    try:
        async with websockets.connect(ws_url) as ws:
            qam_ws_activo = ws
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
                    elif cmd == "perfil":
                        ejecutar_ally(["perfil", str(int(payload["val"]))])
                    elif cmd == "tdp":
                        b_pico = "1" if payload.get("boost_pico") else "0"
                        ejecutar_ally(["tdp", str(int(payload.get("val", 17))), b_pico])
                    elif cmd == "boost":
                        ejecutar_ally(["boost", "1" if payload["val"] else "0"])
                    elif cmd == "curva":
                        pts_csv = ",".join(str(int(x)) for x in payload["val"])
                        ejecutar_ally(["guardar_curva", pts_csv])
    except Exception:
        pass
    finally:
        if qam_ws_activo:
            qam_ws_activo = None


async def bucle_principal():
    tareas = {}
    while True:
        try:
            with urllib.request.urlopen("http://localhost:8080/json", timeout=2) as resp:
                targets = json.loads(resp.read().decode())
            for t in targets:
                title = t.get("title", "")
                tid = t.get("id")
                ws_url = t.get("webSocketDebuggerUrl")
                if not tid or not ws_url:
                    continue
                if t.get("type") == "page" and title.startswith("QuickAccess"):
                    if tid not in tareas or tareas[tid].done():
                        tareas[tid] = asyncio.create_task(manejar_target(ws_url))
                elif title == "SharedJSContext":
                    if tid not in tareas or tareas[tid].done():
                        tareas[tid] = asyncio.create_task(manejar_shared(ws_url))
        except Exception:
            pass
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(bucle_principal())


