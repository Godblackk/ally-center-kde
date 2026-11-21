import QtQuick
import QtCore
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    //lee los valores de tdp y energia guardados por KDE Plasma al iniciar
    property string tituloConsola: "Center ROG Ally X"
    property int tabActual: Plasmoid.configuration.tabActual
    property int perfilEnergia: Plasmoid.configuration.perfilEnergia
    property bool tdpManual: Plasmoid.configuration.tdpManual
    property int tdpWatts: Plasmoid.configuration.tdpWatts
    property bool cpuBoost: Plasmoid.configuration.cpuBoost
    property bool cuidadoBateria: Plasmoid.configuration.cuidadoBateria
    property string apuWatts: "0.0"
    property int ultimoPctCurva: -1
    property bool bloqueadoSync: false
    Timer {
        id: timerBloqueo
        interval: 3000
        onTriggered: root.bloqueadoSync = false
    }
    function pausarSync() {
        root.bloqueadoSync = true
        timerBloqueo.restart()
    }
    property bool acConectado: false
    property int maxTdpActual: root.acConectado ? 30 : 25




    // Lee los valores de ventiladores guardados por KDE Plasma al iniciar
    property int modoActual: Plasmoid.configuration.modoActual
    property int vistaCurva: Plasmoid.configuration.vistaCurva
    property bool vincularFans: Plasmoid.configuration.vincularFans
    property int velAmbos: Plasmoid.configuration.velAmbos
    property int velCpu: Plasmoid.configuration.velCpu
    property int velGpu: Plasmoid.configuration.velGpu

    property var curvaTemps: Array(30, 40, 50, 60, 70, 80, 90, 100)
    property var curvaPuntos: Array(15, 25, 40, 55, 70, 85, 95, 100)

    property int cpuRpm: 0
    property int gpuRpm: 0
    property int cpuTemp: 0
    property string rgbModo: "fijo"
    property int rgbR: 255
    property int rgbG: 0
    property int rgbB: 60
    property int rgbBrillo: 80
    property int rgbBrilloPrevio: 80

    function aplicarRgb() {
        pausarSync()
        ejecutarComando("rgb " + root.rgbModo + " " + root.rgbR + " " + root.rgbG + " " + root.rgbB + " " + root.rgbBrillo)
    }

    Timer {
        id: timerRgbLive
        interval: 60
        onTriggered: ejecutarComando("rgb_live " + root.rgbModo + " " + root.rgbR + " " + root.rgbG + " " + root.rgbB + " " + root.rgbBrillo)
    }

    function aplicarRgbEnVivo() {
        pausarSync()
        if (!timerRgbLive.running) timerRgbLive.start()
    }


    property string scriptPath: StandardPaths.writableLocation(StandardPaths.GenericDataLocation) + "/plasma/plasmoids/org.ally.center/contents/scripts/ally_center.py"

    // Guarda todos los ajustes actuales en Plasma
    function guardarConfig() {
        Plasmoid.configuration.modoActual = root.modoActual
        Plasmoid.configuration.vistaCurva = root.vistaCurva
        Plasmoid.configuration.vincularFans = root.vincularFans
        Plasmoid.configuration.velAmbos = root.velAmbos
        Plasmoid.configuration.velCpu = root.velCpu
        Plasmoid.configuration.velGpu = root.velGpu
        Plasmoid.configuration.curvaGuardada = root.curvaPuntos.join(",")
        Plasmoid.configuration.tabActual = root.tabActual
        Plasmoid.configuration.perfilEnergia = root.perfilEnergia
        Plasmoid.configuration.tdpManual = root.tdpManual
        Plasmoid.configuration.tdpWatts = root.tdpWatts
        Plasmoid.configuration.cpuBoost = root.cpuBoost
        Plasmoid.configuration.cuidadoBateria = root.cuidadoBateria

    }

    function aplicarTodoEnergia() {
        pausarSync()
        if (root.tdpManual) {
            ejecutarComando("tdp " + root.tdpWatts)
        } else {
            ejecutarComando("perfil " + root.perfilEnergia)
        }
        aplicarEstadoActual()
    }


    // Aplica el modo activo al chip de la Ally X
    function aplicarEstadoActual() {
        if (root.modoActual === 0) {
            ejecutarComando("auto")
        } else if (root.modoActual === 1) {
            if (root.vincularFans) {
                ejecutarComando("ambos " + root.velAmbos)
            } else {
                ejecutarComando("cpu_fan " + root.velCpu)
                ejecutarComando("gpu_fan " + root.velGpu)
            }
        } else if (root.modoActual === 2) {
            aplicarCurva()
        }
    }

    // Al arrancar el escritorio o reiniciar Plasma: carga la curva y la aplica
    Component.onCompleted: {
        ejecutarComando("estado")

    }

    Plasma5Support.DataSource {
        id: ejecutor
        engine: "executable"
        connectedSources: Array()
        onNewData: (sourceName, data) => {
            if (sourceName.indexOf("estado") !== -1 && data.stdout) {
                try {
                    let info = JSON.parse(data.stdout)
                    if (info.modelo) root.tituloConsola = info.modelo
                        root.cpuRpm = info.cpu_rpm || 0
                        root.gpuRpm = info.gpu_rpm || 0
                        root.cpuTemp = info.temp || 0
                        sincronizarCurvaDinamica()
                        root.apuWatts = info.watts || "0.0"

                        if (!root.bloqueadoSync) {
                            if (info.perfil !== undefined) root.perfilEnergia = info.perfil
                            if (info.tdp !== undefined) root.tdpWatts = info.tdp
                            if (info.tdp_manual !== undefined) root.tdpManual = info.tdp_manual
                            if (info.boost !== undefined) root.cpuBoost = info.boost
                            if (info.bateria_80 !== undefined) root.cuidadoBateria = info.bateria_80

                            if (info.curva && info.curva.length === 8) {
                                root.curvaPuntos = info.curva
                                if (typeof graficoCanvas !== "undefined" && graficoCanvas) {
                                    graficoCanvas.requestPaint()
                                }
                            }
                            if (info.modo_fan !== undefined) {
                                root.modoActual = (info.modo_fan === "auto") ? 0 : (info.modo_fan === "manual" ? 1 : 2)
                            }
                            if (info.rgb_modo !== undefined) root.rgbModo = info.rgb_modo
                            if (info.rgb && info.rgb.length === 3) {
                                    root.rgbR = info.rgb[0]; root.rgbG = info.rgb[1]; root.rgbB = info.rgb[2]
                            }
                            if (info.rgb_brillo !== undefined) root.rgbBrillo = info.rgb_brillo

                        }

                        if (info.ac_conectado !== undefined) {
                            let cambioAc = (root.acConectado !== info.ac_conectado)
                            root.acConectado = info.ac_conectado
                            if (!root.acConectado && root.tdpWatts > 25) {
                                root.tdpWatts = 25
                                if (root.tdpManual) ejecutarComando("tdp 25")
                            }
                            if (cambioAc && !root.tdpManual && root.perfilEnergia === 2) {
                                root.tdpWatts = root.acConectado ? 30 : 25
                                ejecutarComando("perfil 2")
                            }
                        }
                } catch (e) {
                    console.warn("AllyCenter error:", e)
                }
            }
            disconnectSource(sourceName)
        }
    }

    function ejecutarComando(args) {
        let rutaLimpia = scriptPath.toString().replace("file://", "")
        let prefijo = (args === "estado") ? "python3 " : "sudo python3 "
        ejecutor.connectSource(prefijo + rutaLimpia + " " + args)
    }

    function aplicarPreset(porcentaje) {
        root.vincularFans = true
        root.velAmbos = porcentaje
        guardarConfig()
        ejecutarComando("ambos " + porcentaje + " guardar")
    }

    function actualizarPuntoCurva(indice, nuevoValor) {
        let valorLimpio = Math.round(nuevoValor / 5) * 5
        valorLimpio = Math.max(0, Math.min(100, valorLimpio))
        let copia = root.curvaPuntos.slice()
        copia[indice] = valorLimpio

        for (let i = indice + 1; i < 8; i++) {
            if (copia[i] < valorLimpio) copia[i] = valorLimpio
        }
        for (let i = indice - 1; i >= 0; i--) {
            if (copia[i] > valorLimpio) copia[i] = valorLimpio
        }

        root.curvaPuntos = copia
        graficoCanvas.requestPaint()
    }

    function aplicarCurva() {
        guardarConfig()
        ejecutarComando("guardar_curva " + root.curvaPuntos.join(","))
        root.ultimoPctCurva = -1
        sincronizarCurvaDinamica()

    }

    function sincronizarCurvaDinamica() {
        if (root.modoActual !== 2) return
            let tempClamped = Math.max(30, Math.min(100, root.cpuTemp))
            let posFraccion = (tempClamped - 30) / 10.0
            let idxBajo = Math.min(6, Math.floor(posFraccion))
            let idxAlto = idxBajo + 1
            let tSegmento = posFraccion - idxBajo

            let v1 = root.curvaPuntos[idxBajo]
            let v2 = root.curvaPuntos[idxAlto]
            let pctExacto = Math.round(v1 + (v2 - v1) * tSegmento)

            if (pctExacto !== root.ultimoPctCurva) {
                root.ultimoPctCurva = pctExacto
                ejecutarComando("ambos " + pctExacto)
            }
    }

    Timer {
        interval: 2000
        running: root.expanded || root.modoActual === 2 || root.rgbModo !== "fijo"
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            ejecutarComando("estado")
            if (root.rgbModo !== "fijo" && root.rgbBrillo > 0) ejecutarComando("rgb_tick")
        }

    }

    compactRepresentation: Kirigami.Icon {
        source: root.tdpManual ? Qt.resolvedUrl("../icons/manual.svg") :
                (root.perfilEnergia === 0 ? Qt.resolvedUrl("../icons/leaf.svg") :
                (root.perfilEnergia === 1 ? Qt.resolvedUrl("../icons/balance.svg") :
                                            Qt.resolvedUrl("../icons/rocket.svg")))
        MouseArea {
            anchors.fill: parent
            onClicked: root.expanded = !root.expanded
        }
    }

    fullRepresentation: Item {
        // Tamaño compacto dinámico según el modo elegido
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.minimumHeight: root.tabActual === 0 ? Kirigami.Units.gridUnit * 17.5 :
        (root.tabActual === 2 ? (root.rgbModo === "fijo" ? Kirigami.Units.gridUnit * 20.5 : Kirigami.Units.gridUnit * 14.5) :
        (root.modoActual === 0 ? Kirigami.Units.gridUnit * 11.5 :
        (root.modoActual === 1 ? Kirigami.Units.gridUnit * 17.5 : Kirigami.Units.gridUnit * 21.5)))
        Layout.preferredHeight: Layout.minimumHeight


        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.mediumSpacing
            spacing: Kirigami.Units.smallSpacing

            // Cabecera compacta
            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents.Label {
                    text: root.tituloConsola
                    font.pointSize: 10
                    font.bold: true
                    Layout.fillWidth: true
                }
                PlasmaComponents.ToolButton {
                    icon.name: "window-pin"
                    icon.width: 16
                    icon.height: 16
                    checkable: true
                    checked: root.hideOnWindowDeactivate === false
                    onToggled: root.hideOnWindowDeactivate = !checked
                }
            }

            // Telemetría compacta en una sola franja
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    PlasmaComponents.Label { text: "CPU"; opacity: 0.6; font.pointSize: 8 }
                    PlasmaComponents.Label { text: root.cpuRpm + " RPM"; font.pointSize: 9; font.bold: true }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    PlasmaComponents.Label { text: "GPU"; opacity: 0.6; font.pointSize: 8 }
                    PlasmaComponents.Label { text: root.gpuRpm + " RPM"; font.pointSize: 9; font.bold: true }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    PlasmaComponents.Label { text: "APU"; opacity: 0.6; font.pointSize: 8 }
                    PlasmaComponents.Label {
                        text: root.cpuTemp + " °C"
                        font.pointSize: 9
                        font.bold: true
                        color: root.cpuTemp >= 80 ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    PlasmaComponents.Label { text: "Consumo"; opacity: 0.6; font.pointSize: 8 }
                    PlasmaComponents.Label { text: root.apuWatts + " W"; font.pointSize: 8.5; font.bold: true }
                }

            }

            // Selector de 3 Pestañas
            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                PlasmaComponents.Button {
                    text: "TDP"
                    icon.name: "speedometer"
                    font.pointSize: 8
                    Layout.fillWidth: true
                    highlighted: root.tabActual === 0
                    onClicked: {
                        root.tabActual = 0
                        guardarConfig()
                    }
                }
                PlasmaComponents.Button {
                    text: "Ventiladores"
                    icon.source: Qt.resolvedUrl("../icons/fan.svg")
                    font.pointSize: 8
                    Layout.fillWidth: true
                    highlighted: root.tabActual === 1
                    onClicked: {
                        root.tabActual = 1
                        guardarConfig()
                        if (root.modoActual === 2 && root.vistaCurva === 0) graficoCanvas.requestPaint()
                    }
                }
                PlasmaComponents.Button {
                    text: "RGB"
                    icon.name: "color-management"
                    font.pointSize: 8
                    Layout.fillWidth: true
                    highlighted: root.tabActual === 2
                    onClicked: {
                        root.tabActual = 2
                        guardarConfig()
                    }
                }

            }


            Kirigami.Separator { Layout.fillWidth: true }


            //SECCION ENERGIA

            // PESTAÑA 0: TDP Y ENERGÍA
            ColumnLayout {
                Layout.fillWidth: true
                visible: root.tabActual === 0
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    enabled: !root.tdpManual
                    opacity: !root.tdpManual ? 1.0 : 0.55
                    PlasmaComponents.Label { text: "Perfil Energía"; font.pointSize: 9; Layout.fillWidth: true }
                    PlasmaComponents.ComboBox {
                        font.pointSize: 8
                        model: root.tdpManual ? ["Manual (Custom)"] : ["Ahorro (13W)", "Equilibrado (17W)", root.acConectado ? "Rendimiento (30W)" : "Rendimiento (25W)"]
                        currentIndex: root.tdpManual ? 0 : root.perfilEnergia
                        onActivated: (index) => {
                            if (!root.tdpManual) {
                                root.perfilEnergia = index
                                let wattsBase = [13, 17, root.acConectado ? 30 : 25]
                                root.tdpWatts = wattsBase[index]
                                guardarConfig()
                                aplicarTodoEnergia()
                            }
                        }
                    }
                }

                Kirigami.Separator { Layout.fillWidth: true }

                PlasmaComponents.Switch {
                    text: "Límite TDP Manual"
                    font.pointSize: 9
                    checked: root.tdpManual
                    onToggled: {
                        root.tdpManual = checked
                        guardarConfig()
                        aplicarTodoEnergia()
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    enabled: root.tdpManual
                    opacity: root.tdpManual ? 1.0 : 0.5
                    spacing: 2

                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents.Label { text: "Límite TDP"; font.pointSize: 9; Layout.fillWidth: true }
                        PlasmaComponents.Label { text: root.tdpWatts + " W"; font.pointSize: 9.5; font.bold: true }
                    }
                    PlasmaComponents.Slider {
                        Layout.fillWidth: true
                        from: 7; to: root.maxTdpActual; stepSize: 1
                        value: root.tdpWatts
                        onMoved: root.tdpWatts = value
                        onPressedChanged: if (!pressed) {
                            guardarConfig()
                            ejecutarComando("tdp " + root.tdpWatts)
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        PlasmaComponents.Button {
                            text: "13W"; font.pointSize: 8; Layout.fillWidth: true
                            highlighted: root.tdpWatts === 13
                            onClicked: { root.tdpWatts = 13; guardarConfig(); ejecutarComando("tdp 13") }
                        }
                        PlasmaComponents.Button {
                            text: "17W"; font.pointSize: 8; Layout.fillWidth: true
                            highlighted: root.tdpWatts === 17
                            onClicked: { root.tdpWatts = 17; guardarConfig(); ejecutarComando("tdp 17") }
                        }
                        PlasmaComponents.Button {
                            text: "25W"; font.pointSize: 8; Layout.fillWidth: true
                            highlighted: root.tdpWatts === 25
                            onClicked: { root.tdpWatts = 25; guardarConfig(); ejecutarComando("tdp 25") }
                        }
                        PlasmaComponents.Button {
                            text: "30W"; font.pointSize: 8; Layout.fillWidth: true
                            enabled: root.acConectado
                            opacity: root.acConectado ? 1.0 : 0.4
                            highlighted: root.tdpWatts === 30
                            onClicked: { pausarSync(); root.tdpWatts = 30; guardarConfig(); ejecutarComando("tdp 30") }
                        }
                    }
                }

                Kirigami.Separator { Layout.fillWidth: true }

                PlasmaComponents.Switch {
                    text: "CPU Boost"
                    font.pointSize: 9
                    checked: root.cpuBoost
                    onToggled: {
                        root.cpuBoost = checked
                        guardarConfig()
                        ejecutarComando("boost " + (checked ? "1" : "0"))
                    }
                }

                PlasmaComponents.Switch {
                    text: "Cuidado de Batería (80%)"
                    font.pointSize: 9
                    checked: root.cuidadoBateria
                    onToggled: {
                        root.cuidadoBateria = checked
                        guardarConfig()
                        ejecutarComando("bateria " + (checked ? "1" : "0"))
                    }
                }
            }


            //SECCION VENTILADORES
            ColumnLayout {
                Layout.fillWidth: true
                visible: root.tabActual === 1
                spacing: Kirigami.Units.smallSpacing
            // Selector de Modo Principal
            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents.Label { text: "Modo"; font.pointSize: 9; Layout.fillWidth: true }
                PlasmaComponents.ComboBox {
                    font.pointSize: 9
                    model: Array("Automático (BIOS)", "Manual (Perfiles)", "Curva Personalizada")
                    currentIndex: root.modoActual
                    onActivated: (index) => {
                        pausarSync()
                        root.modoActual = index
                        guardarConfig()
                        if (index === 0) {
                            ejecutarComando("auto")
                        } else if (index === 1) {
                            if (root.vincularFans) {
                                ejecutarComando("ambos " + root.velAmbos + " guardar")
                            } else {
                                ejecutarComando("cpu_fan " + root.velCpu)
                                ejecutarComando("gpu_fan " + root.velGpu)
                            }
                        } else if (index === 2) {
                            aplicarCurva()
                            graficoCanvas.requestPaint()
                        }
                    }
                }
            }



            // ==========================================
            // SECCIÓN 1: MANUAL (PERFILES)
            // ==========================================
            ColumnLayout {
                Layout.fillWidth: true
                visible: root.modoActual === 1
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Separator { Layout.fillWidth: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    PlasmaComponents.Button {
                        text: "Silencioso"
                        font.pointSize: 8
                        Layout.fillWidth: true
                        highlighted: root.vincularFans && root.velAmbos === 30
                        onClicked: aplicarPreset(30)
                    }
                    PlasmaComponents.Button {
                        text: "Equilibrado"
                        font.pointSize: 8
                        Layout.fillWidth: true
                        highlighted: root.vincularFans && root.velAmbos === 60
                        onClicked: aplicarPreset(60)
                    }
                    PlasmaComponents.Button {
                        text: "Turbo"
                        font.pointSize: 8
                        Layout.fillWidth: true
                        highlighted: root.vincularFans && root.velAmbos === 90
                        onClicked: aplicarPreset(90)
                    }
                }

                PlasmaComponents.Switch {
                    text: "Vincular CPU + GPU"
                    font.pointSize: 9
                    checked: root.vincularFans
                    onToggled: {
                        root.vincularFans = checked
                        guardarConfig()
                        if (checked) {
                            ejecutarComando("ambos " + root.velAmbos)
                        } else {
                            ejecutarComando("cpu_fan " + root.velCpu)
                            ejecutarComando("gpu_fan " + root.velGpu)
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    visible: root.vincularFans
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents.Label { text: "Ambos"; font.pointSize: 9; Layout.fillWidth: true }
                        PlasmaComponents.Label { text: root.velAmbos + "%"; font.pointSize: 9; font.bold: true }
                    }
                    PlasmaComponents.Slider {
                        Layout.fillWidth: true
                        from: 0; to: 100; stepSize: 5
                        value: root.velAmbos
                        onMoved: root.velAmbos = value
                        onPressedChanged: if (!pressed) {
                            guardarConfig()
                            ejecutarComando("ambos " + root.velAmbos + " guardar")
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    visible: !root.vincularFans
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents.Label { text: "CPU Fan"; font.pointSize: 9; Layout.fillWidth: true }
                        PlasmaComponents.Label { text: root.velCpu + "%"; font.pointSize: 9; font.bold: true }
                    }
                    PlasmaComponents.Slider {
                        Layout.fillWidth: true
                        from: 0; to: 100; stepSize: 5
                        value: root.velCpu
                        onMoved: root.velCpu = value
                        onPressedChanged: if (!pressed) ejecutarComando("cpu_fan " + root.velCpu)
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents.Label { text: "GPU Fan"; font.pointSize: 9; Layout.fillWidth: true }
                        PlasmaComponents.Label { text: root.velGpu + "%"; font.pointSize: 9; font.bold: true }
                    }
                    PlasmaComponents.Slider {
                        Layout.fillWidth: true
                        from: 0; to: 100; stepSize: 5
                        value: root.velGpu
                        onMoved: root.velGpu = value
                        onPressedChanged: if (!pressed) ejecutarComando("gpu_fan " + root.velGpu)
                    }
                }
            }

            // ==========================================
            // SECCIÓN 2: CURVA PERSONALIZADA
            // ==========================================
            ColumnLayout {
                Layout.fillWidth: true
                visible: root.modoActual === 2
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Separator { Layout.fillWidth: true }

                // Selector Gráfico vs Deslizadores + Botón Restaurar
                RowLayout {
                    Layout.fillWidth: true
                    PlasmaComponents.Label { text: "Vista"; font.pointSize: 9; Layout.fillWidth: true }

                    PlasmaComponents.ToolButton {
                        icon.name: "edit-undo"
                        icon.width: 16
                        icon.height: 16
                        PlasmaComponents.ToolTip.visible: hovered
                        PlasmaComponents.ToolTip.text: "Restaurar curva por defecto"
                        onClicked: {
                            root.curvaPuntos = Array(15, 25, 40, 55, 70, 85, 95, 100)
                            root.aplicarCurva()
                            graficoCanvas.requestPaint()
                        }
                    }

                    PlasmaComponents.ComboBox {
                        font.pointSize: 8
                        model: Array("Curva Manual", "Deslizadores")
                        currentIndex: root.vistaCurva
                        onActivated: (index) => {
                            root.vistaCurva = index
                            guardarConfig()
                            if (index === 0) graficoCanvas.requestPaint()
                        }
                    }
                }

                // VISTA A: GRÁFICO CON EJE Y (100% / 50% / 0%) Y EJE X (30° a 100°)
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 11
                    visible: root.vistaCurva === 0
                    color: Qt.rgba(0, 0, 0, 0.25)
                    radius: 6
                    border.color: Qt.rgba(1, 1, 1, 0.15)
                    border.width: 1

                    Connections {
                        target: root
                        function onCurvaPuntosChanged() {
                            graficoCanvas.requestPaint()
                        }
                        function onCpuTempChanged() {
                            if (graficoCanvas.visible) graficoCanvas.requestPaint()
                        }
                    }

                    // Línea azul y cuadrícula horizontal
                    Canvas {
                        id: graficoCanvas
                        anchors.fill: parent
                        onVisibleChanged: {
                            if (visible) {
                                opacity = 0
                                timerPintar.restart()
                            }
                        }
                        Timer {
                            id: timerPintar
                            interval: 120
                            onTriggered: {
                                graficoCanvas.requestPaint()
                                graficoCanvas.opacity = 1
                            }
                        }

                        onPaint: {
                            let ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)

                            if (puntosRepeater.count < 8) return

                                // Líneas horizontales alineadas con 100%, 50% y 0%
                                ctx.strokeStyle = "rgba(255, 255, 255, 0.12)"
                                ctx.lineWidth = 1
                                let topY = 14
                                let botY = height - 26
                                let izqX = 34
                                let derX = width - 10
                                for (let k = 0; k <= 5; k++) {
                                    let y = topY + (k / 5.0) * (botY - topY)
                                    ctx.beginPath()
                                    ctx.moveTo(izqX, y)
                                    ctx.lineTo(derX, y)
                                    ctx.stroke()

                                }

                                // Línea azul pasando por el centro exacto de cada círculo
                                ctx.strokeStyle = "#3daee9"
                                ctx.lineWidth = 2.5
                                ctx.beginPath()
                                for (let i = 0; i < 8; i++) {
                                    let item = puntosRepeater.itemAt(i)
                                    if (item && item.circulo) {
                                        let centro = mapFromItem(item.circulo, 7, 7)
                                        if (i === 0) ctx.moveTo(centro.x, centro.y)
                                            else ctx.lineTo(centro.x, centro.y)
                                    }
                                }
                                ctx.stroke()

                                // ==========================================
                                // MARCADOR DINÁMICO DE TEMPERATURA ACTUAL
                                // ==========================================
                                let tempClamped = Math.max(30, Math.min(100, root.cpuTemp))
                                let posFraccion = (tempClamped - 30) / 10.0
                                let idxBajo = Math.min(6, Math.floor(posFraccion))
                                let idxAlto = idxBajo + 1
                                let tSegmento = posFraccion - idxBajo

                                let itemBajo = puntosRepeater.itemAt(idxBajo)
                                let itemAlto = puntosRepeater.itemAt(idxAlto)
                                if (itemBajo && itemBajo.circulo && itemAlto && itemAlto.circulo) {
                                    let p1 = mapFromItem(itemBajo.circulo, 7, 7)
                                    let p2 = mapFromItem(itemAlto.circulo, 7, 7)
                                    let curX = p1.x + (p2.x - p1.x) * tSegmento
                                    let curY = p1.y + (p2.y - p1.y) * tSegmento

                                    // Halo exterior semitransparente
                                    ctx.fillStyle = root.cpuTemp >= 80 ? "rgba(255, 85, 85, 0.35)" : "rgba(255, 170, 0, 0.35)"
                                    ctx.beginPath()
                                    ctx.arc(curX, curY, 9, 0, Math.PI * 2)
                                    ctx.fill()

                                    // Punto central sólido (naranja normal, rojo si >= 80°C)
                                    ctx.fillStyle = root.cpuTemp >= 80 ? "#ff5555" : "#ffaa00"
                                    ctx.beginPath()
                                    ctx.arc(curX, curY, 5, 0, Math.PI * 2)
                                    ctx.fill()

                                    ctx.strokeStyle = "#ffffff"
                                    ctx.lineWidth = 1.5
                                    ctx.stroke()
                                }
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 2

                        // EJE Y: Etiquetas de 100% a 0% de 20 en 20
                        ColumnLayout {
                            Layout.fillHeight: true
                            Layout.fillWidth: false
                            Layout.preferredWidth: 28
                            Layout.bottomMargin: 13
                            spacing: 0

                            Repeater {
                                model: Array("100%", "80%", "60%", "40%", "20%", "0%")
                                delegate: Item {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: index < 5
                                    Layout.preferredHeight: index === 5 ? 10 : 1

                                    PlasmaComponents.Label {
                                        text: modelData
                                        font.pointSize: 7
                                        opacity: 0.7
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                    }
                                }
                            }
                        }



                        // 8 Columnas con ancho matemático exacto (ancho disponible / 8)
                        Row {
                            id: filaNodos
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 0
                            onWidthChanged: graficoCanvas.requestPaint()

                            Repeater {
                                id: puntosRepeater
                                model: 8
                                ColumnLayout {
                                    id: colItem
                                    property alias circulo: puntoVisual
                                    width: filaNodos.width / 8
                                    height: filaNodos.height
                                    spacing: 2

                                    PlasmaComponents.Slider {
                                        id: nodoSlider
                                        orientation: Qt.Vertical
                                        topPadding: 0
                                        bottomPadding: 0
                                        implicitWidth: 22
                                        Layout.preferredWidth: 22
                                        Layout.fillHeight: true
                                        Layout.alignment: Qt.AlignHCenter
                                        from: 0; to: 100; stepSize: 5
                                        value: root.curvaPuntos[index]
                                        onMoved: root.actualizarPuntoCurva(index, value)
                                        onPressedChanged: if (!pressed) root.aplicarCurva()

                                        // Línea vertical gris centrada
                                        Rectangle {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            y: 7
                                            height: parent.height - 14
                                            width: 1
                                            color: Qt.rgba(1, 1, 1, 0.12)
                                            z: -1
                                        }

                                        background: Item {
                                            implicitWidth: 22
                                            implicitHeight: 100
                                        }

                                        handle: Rectangle {
                                            id: puntoVisual
                                            x: (nodoSlider.width - width) / 2
                                            y: nodoSlider.topPadding + nodoSlider.visualPosition * (nodoSlider.availableHeight - height)
                                            width: 14
                                            height: 14
                                            radius: 7
                                            color: nodoSlider.pressed ? "#3daee9" : "#ffffff"
                                            border.color: "#3daee9"
                                            border.width: 2

                                            // Muestra el porcentaje flotando solo mientras arrastras el punto
                                            Rectangle {
                                                visible: nodoSlider.pressed
                                                anchors.bottom: parent.top
                                                anchors.bottomMargin: 4
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                width: 30
                                                height: 16
                                                radius: 4
                                                color: "#3daee9"
                                                PlasmaComponents.Label {
                                                    anchors.centerIn: parent
                                                    text: root.curvaPuntos[index] + "%"
                                                    font.pointSize: 7
                                                    font.bold: true
                                                    color: "#ffffff"
                                                }
                                            }
                                        }
                                    }

                                    // EJE X: Temperaturas abajo
                                    PlasmaComponents.Label {
                                        text: root.curvaTemps[index] + "°"
                                        font.pointSize: 7
                                        opacity: 0.7
                                        Layout.alignment: Qt.AlignHCenter
                                    }
                                }
                            }
                        }
                    }
                }
                // VISTA B: DESLIZADORES EN CASCADA
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: root.vistaCurva === 1
                    spacing: 0

                    Repeater {
                        model: 8
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            PlasmaComponents.Label {
                                text: root.curvaTemps[index] + " °C"
                                font.pointSize: 8
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 2.3
                                font.bold: true
                            }
                            PlasmaComponents.Slider {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 18
                                from: 0; to: 100; stepSize: 5
                                value: root.curvaPuntos[index]
                                onMoved: root.actualizarPuntoCurva(index, value)
                                onPressedChanged: if (!pressed) root.aplicarCurva()
                            }
                            PlasmaComponents.Label {
                                text: root.curvaPuntos[index] + "%"
                                font.pointSize: 8
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 2.2
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }
                }
            }
        }

                // PESTAÑA 3: ILUMINACIÓN RGB
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: root.tabActual === 2
                    spacing: Kirigami.Units.smallSpacing

                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents.Switch {
                            text: "Iluminación Joysticks"
                            font.pointSize: 9
                            Layout.fillWidth: true
                            checked: root.rgbBrillo > 0
                            onToggled: {
                                if (checked) {
                                    root.rgbBrillo = root.rgbBrilloPrevio > 0 ? root.rgbBrilloPrevio : 80
                                } else {
                                    root.rgbBrilloPrevio = root.rgbBrillo
                                    root.rgbBrillo = 0
                                }
                                root.aplicarRgb()
                            }
                        }
                        Rectangle {
                            width: 22; height: 22; radius: 11
                            color: {
                                if (root.rgbBrillo === 0) return "#222222"
                                    if (root.rgbModo === "temp") {
                                        if (root.cpuTemp < 55) return Qt.rgba(0, 210/255, 1, 1)
                                            if (root.cpuTemp < 72) return Qt.rgba(40/255, 230/255, 90/255, 1)
                                                if (root.cpuTemp < 84) return Qt.rgba(1, 110/255, 0, 1)
                                                    return Qt.rgba(1, 15/255, 15/255, 1)
                                    }
                                    if (root.rgbModo === "hora") {
                                        let h = new Date().getHours()
                                        if (h >= 7 && h < 13) return Qt.rgba(1, 235/255, 195/255, 1)
                                            if (h >= 13 && h < 20) return Qt.rgba(0, 210/255, 1, 1)
                                                return Qt.rgba(1, 35/255, 20/255, 1)
                                    }
                                    if (root.rgbModo === "bateria") return Qt.rgba(35/255, 225/255, 85/255, 1)
                                        return Qt.rgba(root.rgbR / 255, root.rgbG / 255, root.rgbB / 255, 1)
                            }
                            border.color: "#ffffff"; border.width: 1.5
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        enabled: root.rgbBrillo > 0
                        opacity: root.rgbBrillo > 0 ? 1.0 : 0.45
                        PlasmaComponents.Label { text: "Modo"; font.pointSize: 9; Layout.fillWidth: true }
                        PlasmaComponents.ComboBox {
                            font.pointSize: 8.5
                            model: Array("Fijo (Color)", "Temperatura APU", "Nivel Batería", "Ciclo Horario")
                            currentIndex: root.rgbModo === "temp" ? 1 : (root.rgbModo === "bateria" ? 2 : (root.rgbModo === "hora" ? 3 : 0))
                            onActivated: (index) => {
                                root.rgbModo = (index === 1) ? "temp" : ((index === 2) ? "bateria" : ((index === 3) ? "hora" : "fijo"))
                                root.aplicarRgb()
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        enabled: root.rgbBrillo > 0
                        opacity: root.rgbBrillo > 0 ? 1.0 : 0.45
                        spacing: 0
                        RowLayout {
                            Layout.fillWidth: true
                            PlasmaComponents.Label { text: "Brillo"; font.pointSize: 9; Layout.fillWidth: true }
                            PlasmaComponents.Label { text: root.rgbBrillo + "%"; font.pointSize: 9; font.bold: true }
                        }
                        PlasmaComponents.Slider {
                            Layout.fillWidth: true
                            from: 5; to: 100; stepSize: 5
                            value: Math.max(5, root.rgbBrillo)
                            onMoved: {
                                root.rgbBrillo = value
                                root.aplicarRgbEnVivo()
                            }
                            onPressedChanged: if (!pressed) {
                                root.rgbBrilloPrevio = root.rgbBrillo
                                root.aplicarRgb()
                            }
                        }
                    }

                    // Controles de color (solo visibles en modo Fijo)
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.rgbModo === "fijo"
                        enabled: root.rgbBrillo > 0 && root.rgbModo === "fijo"
                        opacity: root.rgbBrillo > 0 ? 1.0 : 0.45
                        spacing: Kirigami.Units.smallSpacing

                        Kirigami.Separator { Layout.fillWidth: true }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Repeater {
                                model: Array(
                                    { r: 255, g: 0, b: 0 },
                                    { r: 0, g: 210, b: 255 },
                                    { r: 165, g: 40, b: 255 },
                                    { r: 30, g: 230, b: 90 },
                                    { r: 255, g: 110, b: 0 },
                                    { r: 255, g: 215, b: 0 },
                                    { r: 255, g: 255, b: 255 }
                                )
                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    height: 22; radius: 6
                                    color: Qt.rgba(modelData.r / 255, modelData.g / 255, modelData.b / 255, 1)
                                    border.color: (root.rgbR === modelData.r && root.rgbG === modelData.g && root.rgbB === modelData.b) ? "#ffffff" : "transparent"
                                    border.width: 2
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: {
                                            root.rgbR = modelData.r; root.rgbG = modelData.g; root.rgbB = modelData.b
                                            root.aplicarRgb()
                                        }
                                    }
                                }
                            }
                        }

                        Repeater {
                            model: Array(
                                { label: "R", col: "#ff5555", prop: "rgbR" },
                                { label: "G", col: "#55dd77", prop: "rgbG" },
                                { label: "B", col: "#44aaff", prop: "rgbB" }
                            )
                            delegate: RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                PlasmaComponents.Label { text: modelData.label; color: modelData.col; font.bold: true; font.pointSize: 8.5; Layout.preferredWidth: 14 }
                                PlasmaComponents.Slider {
                                    Layout.fillWidth: true; Layout.preferredHeight: 18
                                    from: 0; to: 255; stepSize: 5
                                    value: root[modelData.prop]
                                    onMoved: {
                                        root[modelData.prop] = value
                                        root.aplicarRgbEnVivo()
                                    }
                                    onPressedChanged: if (!pressed) root.aplicarRgb()
                                }
                                PlasmaComponents.Label { text: root[modelData.prop]; font.pointSize: 8; Layout.preferredWidth: 24; horizontalAlignment: Text.AlignRight }
                            }
                        }
                    }
                }
            Item { Layout.fillHeight: true }
        }
    }
}

