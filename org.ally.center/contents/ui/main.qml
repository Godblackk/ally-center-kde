import QtQuick
import QtCore
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami
import "i18n.js" as I18n


PlasmoidItem {
    id: root
    readonly property string lang: I18n.detectarIdioma(Qt.locale().name)
    function t(clave) { return I18n.tr(lang, clave) }
    onExpandedChanged: if (root.expanded) ejecutarComando("estado")



    //lee los valores de tdp y energia guardados por KDE Plasma al iniciar
    property string tituloConsola: "Center ROG Ally X"
    property int tabActual: Plasmoid.configuration.tabActual
    property int perfilEnergia: Plasmoid.configuration.perfilEnergia
    property bool tdpManual: Plasmoid.configuration.tdpManual
    property bool tdpBoost: false
    property int tdpWatts: Plasmoid.configuration.tdpWatts
    property bool cpuBoost: Plasmoid.configuration.cpuBoost
    property bool cuidadoBateria: Plasmoid.configuration.cuidadoBateria
    property string apuWatts: "0.0"
    property int ultimoPctCurva: -1
    property bool bloqueadoSync: false
    property bool syncModos: true

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
    property int batPct: 100
    property string batWatts: "0.0"
    property string batTiempo: "AC"
    property int maxTdpActual: root.acConectado ? 30 : 25
    property int ultimoPerfilKernel: -1


    // Lee los valores de ventiladores guardados por KDE Plasma al iniciar
    property int modoActual: Plasmoid.configuration.modoActual
    property int vistaCurva: Plasmoid.configuration.vistaCurva
    property bool vincularFans: Plasmoid.configuration.vincularFans
    property int velAmbos: Plasmoid.configuration.velAmbos
    property int velCpu: Plasmoid.configuration.velCpu
    property int velGpu: Plasmoid.configuration.velGpu

    property var curvaTemps: Array(30, 40, 50, 60, 70, 80, 90, 100)
    property var curvaPuntos: Array(15, 25, 40, 55, 70, 85, 95, 100)
    signal curvaActualizada()

    property int cpuRpm: 0
    property int gpuRpm: 0
    property int cpuTemp: 0
    property string rgbModo: "fijo"
    property int rgbR: 255
    property int rgbG: 0
    property int rgbB: 60
    property int rgbBrillo: 80
    property int rgbVel: 2
    property int rgbBrilloPrevio: 2

    function aplicarRgb() {
        pausarSync()
        ejecutarComando("rgb " + root.rgbModo + " " + root.rgbR + " " + root.rgbG + " " + root.rgbB + " " + root.rgbBrillo + " 1 " + root.rgbVel)
    }

    Timer {
        id: timerRgbLive
        interval: 80
        repeat: false
        onTriggered: {
            pausarSync()
            ejecutarComando("rgb_live " + root.rgbModo + " " + root.rgbR + " " + root.rgbG + " " + root.rgbB + " " + root.rgbBrillo + " " + root.rgbVel)
        }
    }

    function aplicarRgbEnVivo() {
        if (root.rgbModo !== "fijo") return;
        pausarSync()
        if (!timerRgbLive.running) timerRgbLive.restart()
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
            if (root.tdpWatts < 25) root.tdpBoost = false
            ejecutarComando("tdp " + root.tdpWatts + (root.tdpBoost ? " 1" : " 0"))
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
        ejecutarComando("aplicar_modo desktop")
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
                    if (info.sync_modos === false && info.perfiles_modo && info.perfiles_modo.desktop) {
                        Object.assign(info, info.perfiles_modo.desktop)
                    }
                    if (info.modelo) root.tituloConsola = info.modelo
                        root.cpuRpm = info.cpu_rpm || 0
                        root.gpuRpm = info.gpu_rpm || 0
                        root.cpuTemp = info.temp || 0
                        root.apuWatts = info.watts || "0.0"
                        if (info.bat_pct !== undefined) root.batPct = info.bat_pct
                        if (info.bat_watts !== undefined) root.batWatts = info.bat_watts
                        if (info.bat_tiempo !== undefined) root.batTiempo = info.bat_tiempo
                        if (!root.bloqueadoSync) {
                            if (info.tdp !== undefined) root.tdpWatts = info.tdp
                            if (info.tdp_manual !== undefined) root.tdpManual = info.tdp_manual
                            if (info.perfil !== undefined) {
                                var pSys = parseInt(info.perfil)
                                var pUi = pSys
                                if ((root.ultimoPerfilKernel !== -1 && pUi !== root.ultimoPerfilKernel) || (root.tdpManual && pSys !== 2)) {
                                    root.tdpManual = false
                                    root.tdpBoost = false
                                    ejecutarComando("perfil " + pSys)
                                }
                                root.ultimoPerfilKernel = pUi
                                root.perfilEnergia = pUi
                            }

                            if (!root.tdpManual) root.tdpWatts = (root.perfilEnergia === 0) ? 13 : (root.perfilEnergia === 1 ? 17 : (root.acConectado ? 30 : 25))
                            if (info.tdp_boost !== undefined) root.tdpBoost = info.tdp_boost
                            if (info.boost !== undefined) root.cpuBoost = info.boost
                            if (info.bateria_80 !== undefined) root.cuidadoBateria = info.bateria_80
                            if (info.curva && info.curva.length === 8) {
                                root.curvaPuntos = info.curva.slice()
                                root.curvaActualizada()
                            }
                            if (info.modo_fan !== undefined) {
                                root.modoActual = (info.modo_fan === "auto") ? 0 : (info.modo_fan === "manual" ? 1 : 2)
                            }
                            if (info.vincular_fans !== undefined) root.vincularFans = info.vincular_fans
                            if (info.fan_pct !== undefined) root.velAmbos = info.fan_pct
                            if (info.cpu_pct !== undefined) root.velCpu = info.cpu_pct
                            if (info.gpu_pct !== undefined) root.velGpu = info.gpu_pct
                            if (info.rgb_modo !== undefined) root.rgbModo = info.rgb_modo
                            if (info.rgb && info.rgb.length === 3) {
                                    root.rgbR = info.rgb[0]; root.rgbG = info.rgb[1]; root.rgbB = info.rgb[2]
                            }
                            if (info.rgb_brillo !== undefined) root.rgbBrillo = info.rgb_brillo
                            if (info.rgb_vel !== undefined) root.rgbVel = info.rgb_vel
                            if (info.sync_modos !== undefined) root.syncModos = info.sync_modos

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
        if (args === "estado") {
            let rutaSh = rutaLimpia.replace("ally_center.py", "estado.sh")
            ejecutor.connectSource("/bin/sh " + rutaSh)
        } else {
            ejecutor.connectSource("sudo python3 " + rutaLimpia + " " + args)
        }
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
        root.curvaActualizada()
    }

    function aplicarCurva() {
        guardarConfig()
        ejecutarComando("guardar_curva " + root.curvaPuntos.join(","))
        root.ultimoPctCurva = -1


    }


    Timer {
        interval: root.expanded ? 1000 : 3000
        running: root.expanded || root.rgbModo !== "fijo"
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            ejecutarComando("estado")
            if ((root.rgbModo === "temp" || root.rgbModo === "bateria" || root.rgbModo === "hora") && root.rgbBrillo > 0) ejecutarComando("rgb_tick")
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
        Layout.minimumHeight: root.tabActual === 0 ? Kirigami.Units.gridUnit * 20.7 :
                                (root.tabActual === 2 ? (root.rgbModo === "fijo" ? Kirigami.Units.gridUnit * 21.7 : Kirigami.Units.gridUnit * 15.7) :
                                (root.modoActual === 0 ? Kirigami.Units.gridUnit * 12.7 :
                                (root.modoActual === 1 ? Kirigami.Units.gridUnit * 18.7 : Kirigami.Units.gridUnit * 22.7)))
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
                Rectangle {
                    radius: 5
                    implicitWidth: lblSyncModos.implicitWidth + 14
                    implicitHeight: 20
                    color: root.syncModos ? Qt.rgba(102/255, 192/255, 244/255, 0.18) : Qt.rgba(245/255, 176/255, 65/255, 0.18)
                    border.color: root.syncModos ? "#66c0f4" : "#f5b041"
                    border.width: 1
                    PlasmaComponents.Label {
                        id: lblSyncModos
                        anchors.centerIn: parent
                        text: root.syncModos ? t("sync_on") : t("per_mode")
                        font.pointSize: 7.5
                        font.bold: true
                        color: root.syncModos ? "#66c0f4" : "#f5b041"
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.syncModos = !root.syncModos
                            pausarSync()
                            ejecutarComando("sync_modos " + (root.syncModos ? "1" : "0"))
                        }
                    }
                }
                PlasmaComponents.ToolButton {
                    icon.name: "window-pin"
                    icon.width: 16
                    icon.height: 16
                    checkable: true
                    checked: root.hideOnWindowDeactivate === false
                    onToggled: root.hideOnWindowDeactivate = !checked
                }
                Rectangle {
                    radius: 5
                    implicitWidth: lblAcBat.implicitWidth + 14
                    implicitHeight: 20
                    color: root.acConectado ? Qt.rgba(88/255, 214/255, 141/255, 0.18) : Qt.rgba(245/255, 176/255, 65/255, 0.18)
                    border.color: root.acConectado ? "#58d68d" : "#f5b041"
                    border.width: 1
                    PlasmaComponents.Label {
                        id: lblAcBat
                        anchors.centerIn: parent
                        text: (root.acConectado ? "🔌 AC · " : "🔋 BAT · ") + root.batPct + "%"
                        font.pointSize: 7.5
                        font.bold: true
                        color: root.acConectado ? "#58d68d" : "#f5b041"
                    }
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
                    PlasmaComponents.Label { text: t("consumption"); opacity: 0.6; font.pointSize: 8 }
                    PlasmaComponents.Label { text: root.apuWatts + " W"; font.pointSize: 8.5; font.bold: true }
                }

            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                PlasmaComponents.Label {
                    property real wBatNum: parseFloat(root.batWatts) || 0
                    text: root.acConectado
                    ? (wBatNum < 0.5 ? ("🔋 " + t("battery") + ": " + (root.cuidadoBateria ? t("limit_80") : t("full"))) : ("⚡ " + t("charging") + ": " + root.batWatts + " W"))
                    : ("🔋 " + t("consumption") + ": " + root.batWatts + " W")
                    font.pointSize: 8
                    opacity: 0.85
                    Layout.fillWidth: true
                }
                PlasmaComponents.Label {
                    property real wBatNum: parseFloat(root.batWatts) || 0
                    text: root.acConectado
                    ? ("🔌 " + t("status") + ": " + (wBatNum < 0.5 ? t("idle") : t("in_charge")))
                    : ("⏳ " + t("remaining") + ": " + root.batTiempo)
                    font.pointSize: 8
                    font.bold: true
                    color: "#3daee9"
                }
            }


            // Selector de 3 Pestañas
            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                PlasmaComponents.Button {
                    text: t("tab_tdp")
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
                    text: t("tab_fans")
                    icon.source: Qt.resolvedUrl("../icons/fan.svg")
                    font.pointSize: 8
                    Layout.fillWidth: true
                    highlighted: root.tabActual === 1
                    onClicked: {
                        root.tabActual = 1
                        guardarConfig()
                        if (root.modoActual === 2 && root.vistaCurva === 0 && typeof graficoCanvas !== "undefined") graficoCanvas.requestPaint()
                    }
                }
                PlasmaComponents.Button {
                    text: t("tab_rgb")
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
                    PlasmaComponents.Label { text: t("power_profile"); font.pointSize: 9; Layout.fillWidth: true }
                    PlasmaComponents.ComboBox {
                        font.pointSize: 8
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 8.5
                        model: root.tdpManual ? [t("manual_custom")] : [t("quiet") + " (13W)", t("balanced") + " (17W)", root.acConectado ? (t("performance") + " (30W)") : (t("performance") + " (25W)")]
                        currentIndex: root.tdpManual ? 0 : root.perfilEnergia
                        onModelChanged: currentIndex = root.tdpManual ? 0 : root.perfilEnergia
                        onActivated: (index) => {
                            pausarSync()
                            root.perfilEnergia = index
                            root.ultimoPerfilKernel = index
                            root.tdpManual = false
                            root.tdpBoost = false
                            root.tdpWatts = (index === 0) ? 13 : (index === 1 ? 17 : (root.acConectado ? 30 : 25))
                            guardarConfig()
                            ejecutarComando("perfil " + index)
                        }
                    }
                }

                Kirigami.Separator { Layout.fillWidth: true }

                PlasmaComponents.Switch {
                    text: t("manual_tdp_limit")
                    font.pointSize: 9
                    checked: root.tdpManual
                    onToggled: {
                        root.tdpManual = checked
                        pausarSync()
                        guardarConfig()
                        if (checked) {
                            root.aplicarTodoEnergia()
                        } else {
                            ejecutarComando("perfil " + root.perfilEnergia)
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    enabled: root.tdpManual
                    opacity: root.tdpManual ? 1.0 : 0.5
                    spacing: 2

                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents.Label { text: t("tdp_limit"); font.pointSize: 9; Layout.fillWidth: true }
                        PlasmaComponents.Label { text: root.tdpWatts + " W"; font.pointSize: 9.5; font.bold: true }
                    }
                    PlasmaComponents.Slider {
                        id: sliderTdp
                        Layout.fillWidth: true
                        from: 7; to: root.maxTdpActual; stepSize: 1
                        value: root.tdpWatts
                        Connections {
                            target: root
                            function onTdpWattsChanged() {
                                if (!sliderTdp.pressed) sliderTdp.value = root.tdpWatts
                            }
                        }
                        onMoved: {
                            root.tdpWatts = Math.round(value)
                            if (root.tdpWatts < 25) root.tdpBoost = false
                        }
                        onPressedChanged: if (!pressed) {
                            timerRgbLive.stop()
                            root.aplicarTodoEnergia()
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
                    PlasmaComponents.Switch {
                        text: t("sppt_fppt_boost")
                        font.pointSize: 9
                        enabled: root.tdpManual && root.tdpWatts >= 25
                        checked: root.tdpBoost
                        onToggled: {
                            pausarSync()
                            root.tdpBoost = checked
                            guardarConfig()
                            ejecutarComando("tdp " + root.tdpWatts + (checked ? " 1" : " 0"))
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
                    text: t("battery_care")
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
                PlasmaComponents.Label { text: t("mode"); font.pointSize: 9; Layout.fillWidth: true }
                PlasmaComponents.ComboBox {
                    font.pointSize: 9
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 8.5
                    model: Array(t("fan_auto_bios"), t("fan_manual_profiles"), t("fan_custom_curve"))
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
                            if (typeof graficoCanvas !== "undefined") graficoCanvas.requestPaint()
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
                        text: t("fan_quiet")
                        font.pointSize: 8
                        Layout.fillWidth: true
                        highlighted: root.vincularFans && root.velAmbos === 30
                        onClicked: aplicarPreset(30)
                    }
                    PlasmaComponents.Button {
                        text: t("fan_balanced")
                        font.pointSize: 8
                        Layout.fillWidth: true
                        highlighted: root.vincularFans && root.velAmbos === 60
                        onClicked: aplicarPreset(60)
                    }
                    PlasmaComponents.Button {
                        text: t("fan_turbo")
                        font.pointSize: 8
                        Layout.fillWidth: true
                        highlighted: root.vincularFans && root.velAmbos === 90
                        onClicked: aplicarPreset(90)
                    }
                }

                PlasmaComponents.Switch {
                    text: t("link_cpu_gpu")
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
                        PlasmaComponents.Label { text: t("both"); font.pointSize: 9; Layout.fillWidth: true }
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
                    PlasmaComponents.Label { text: t("view"); font.pointSize: 9; Layout.fillWidth: true }

                    PlasmaComponents.ToolButton {
                        icon.name: "edit-undo"
                        icon.width: 16
                        icon.height: 16
                        PlasmaComponents.ToolTip.visible: hovered
                        PlasmaComponents.ToolTip.text: t("reset_curve_tip")
                        onClicked: {
                            root.curvaPuntos = Array(15, 25, 40, 55, 70, 85, 95, 100)
                            root.curvaActualizada()
                            root.aplicarCurva()
                        }
                    }

                    PlasmaComponents.ComboBox {
                        font.pointSize: 8
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 8.5
                        model: Array(t("manual_curve"), t("sliders"))
                        currentIndex: root.vistaCurva
                        onActivated: (index) => {
                            root.vistaCurva = index
                            guardarConfig()
                            if (index === 0) graficoCanvas.requestPaint()
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    PlasmaComponents.Button {
                        text: t("fan_quiet")
                        font.pointSize: 8
                        Layout.fillWidth: true
                        Layout.preferredHeight: 26
                        onClicked: {
                            root.curvaPuntos = Array(5, 10, 15, 20, 30, 40, 50, 60)
                            root.curvaActualizada()
                            root.aplicarCurva()
                        }
                    }
                    PlasmaComponents.Button {
                        text: t("fan_balanced")
                        font.pointSize: 8
                        Layout.fillWidth: true
                        Layout.preferredHeight: 26
                        onClicked: {
                            root.curvaPuntos = Array(15, 25, 40, 55, 70, 85, 95, 100)
                            root.curvaActualizada()
                            root.aplicarCurva()
                        }
                    }
                    PlasmaComponents.Button {
                        text: t("fan_turbo")
                        font.pointSize: 8
                        Layout.fillWidth: true
                        Layout.preferredHeight: 26
                        onClicked: {
                            root.curvaPuntos = Array(30, 45, 60, 75, 90, 100, 100, 100)
                            root.curvaActualizada()
                            root.aplicarCurva()
                        }
                    }
                }

                // VISTA A: GRÁFICO CON EJE Y (100% / 50% / 0%) Y EJE X (30° a 100°)
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 9.5
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
                        Connections {
                            target: root
                            function onCurvaActualizada() { graficoCanvas.requestPaint() }
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
                                        Connections {
                                            target: root
                                            function onCurvaActualizada() {
                                                if (!nodoSlider.pressed) nodoSlider.value = root.curvaPuntos[index]
                                            }
                                        }
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
                        id: repCurvaSliders
                        model: 8
                        RowLayout {
                            property alias sliderVal: slCurva.value
                            Layout.fillWidth: true
                            spacing: 4
                            PlasmaComponents.Label {
                                text: root.curvaTemps[index] + " °C"
                                font.pointSize: 8
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 2.3
                                font.bold: true
                            }
                            PlasmaComponents.Slider {
                                id: slCurva
                                Layout.fillWidth: true
                                Layout.preferredHeight: 18
                                from: 0; to: 100; stepSize: 5
                                Component.onCompleted: slCurva.value = root.curvaPuntos[index]
                                Connections {
                                    target: root
                                    function onCurvaActualizada() {
                                        if (!slCurva.pressed) slCurva.value = root.curvaPuntos[index]
                                    }
                                }
                                onMoved: {
                                    root.pausarSync()
                                    root.actualizarPuntoCurva(index, value)
                                }
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
                            text: t("joystick_lighting")
                            font.pointSize: 9
                            Layout.fillWidth: true
                            checked: root.rgbBrillo > 0
                            onToggled: {
                                if (checked) {
                                    root.rgbBrillo = root.rgbBrilloPrevio > 0 ? root.rgbBrilloPrevio : 2
                                } else {
                                    root.rgbBrilloPrevio = root.rgbBrillo
                                    root.rgbBrillo = 0
                                }
                                root.aplicarRgb()
                            }
                        }
                        Rectangle {
                            id: rgbIndicadorCirculo
                            width: 22; height: 22; radius: 11
                            clip: true
                            color: {
                                if (root.rgbBrillo === 0) return "#222222"
                                    if (root.rgbModo === "temp") {
                                    if (root.cpuTemp <= 35) return Qt.rgba(0, 210/255, 1, 1)
                                    if (root.cpuTemp <= 65) return Qt.rgba(0, 1, 0, 1)
                                    if (root.cpuTemp <= 75) return Qt.rgba(1, 165/255, 0, 1)
                                    if (root.cpuTemp <= 85) return Qt.rgba(1, 110/255, 0, 1)
                                    return Qt.rgba(1, 0, 0, 1)
                                }

                                if (root.rgbModo === "hora") {
                                    let h = new Date().getHours()
                                    if (h >= 7 && h < 13) return Qt.rgba(1, 1, 1, 1)
                                        if (h >= 13 && h < 20) return Qt.rgba(0, 210/255, 1, 1)
                                            return Qt.rgba(1, 0, 0, 1)
                                }
                                if (root.rgbModo === "bateria") {
                                    if (root.acConectado || root.batPct > 60) return Qt.rgba(0, 1, 0, 1)
                                    if (root.batPct >= 25) return Qt.rgba(1, 165/255, 0, 1)
                                    if (root.batPct > 10) return Qt.rgba(1, 110/255, 0, 1)
                                    return Qt.rgba(1, 0, 0, 1)
                                }
                                return Qt.rgba(root.rgbR / 255, root.rgbG / 255, root.rgbB / 255, 1)
                            }
                            border.color: "#ffffff"; border.width: 1.5

                            // Efecto visual arcoíris para Ciclo de Colores y Arcoíris
                            Rectangle {
                                anchors.fill: parent
                                radius: 11
                                visible: root.rgbBrillo > 0 && (root.rgbModo === "ciclo" || root.rgbModo === "arcoiris")
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0.0; color: "#ff0000" }
                                    GradientStop { position: 0.33; color: "#00ff00" }
                                    GradientStop { position: 0.66; color: "#00d2ff" }
                                    GradientStop { position: 1.0; color: "#a528ff" }
                                }
                                RotationAnimator on rotation {
                                    from: 0; to: 360
                                    duration: root.rgbVel === 1 ? 4500 : (root.rgbVel === 3 ? 1200 : 2500)
                                    loops: Animation.Infinite
                                    running: root.expanded && root.rgbBrillo > 0 && (root.rgbModo === "ciclo" || root.rgbModo === "arcoiris")
                                }
                            }

                            // Efecto visual de pulso suave para Respiración
                            SequentialAnimation on opacity {
                                loops: Animation.Infinite
                                running: root.expanded && root.rgbBrillo > 0 && root.rgbModo === "respiracion"
                                NumberAnimation { from: 1.0; to: 0.25; duration: root.rgbVel === 1 ? 1800 : (root.rgbVel === 3 ? 550 : 1000) }
                                NumberAnimation { from: 0.25; to: 1.0; duration: root.rgbVel === 1 ? 1800 : (root.rgbVel === 3 ? 550 : 1000) }
                            }
                            onOpacityChanged: if (root.rgbModo !== "respiracion" && opacity !== 1.0) opacity = 1.0
                        }

                    }

                    RowLayout {
                        Layout.fillWidth: true
                        enabled: root.rgbBrillo > 0
                        opacity: root.rgbBrillo > 0 ? 1.0 : 0.45
                        PlasmaComponents.Label { text: t("mode"); font.pointSize: 9; Layout.fillWidth: true }
                        PlasmaComponents.ComboBox {
                            font.pointSize: 8.5
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 8.5
                            readonly property var modosLista: Array("fijo", "respiracion", "ciclo", "arcoiris", "temp", "bateria", "hora")
                            model: [t("rgb_fixed_color"), t("rgb_breathing"), t("rgb_color_cycle"), t("rgb_rainbow"), t("rgb_apu_temp"), t("rgb_bat_level"), t("rgb_time_cycle")]
                            currentIndex: Math.max(0, modosLista.indexOf(root.rgbModo))
                            onActivated: (index) => {
                                root.rgbModo = modosLista[index]
                                root.aplicarRgb()
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.rgbModo !== "ciclo" && root.rgbModo !== "arcoiris"
                        enabled: root.rgbBrillo > 0
                        opacity: root.rgbBrillo > 0 ? 1.0 : 0.45
                        spacing: 0
                        RowLayout {
                            Layout.fillWidth: true
                            PlasmaComponents.Label { text: t("brightness"); font.pointSize: 9; Layout.fillWidth: true }
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
                                timerRgbLive.stop()
                                root.rgbBrilloPrevio = root.rgbBrillo
                                root.aplicarRgb()
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.rgbModo === "respiracion" || root.rgbModo === "ciclo" || root.rgbModo === "arcoiris"
                        enabled: root.rgbBrillo > 0
                        opacity: root.rgbBrillo > 0 ? 1.0 : 0.45
                        spacing: 0
                        RowLayout {
                            Layout.fillWidth: true
                            PlasmaComponents.Label { text: t("speed"); font.pointSize: 9; Layout.fillWidth: true }
                            PlasmaComponents.Label {
                                text: root.rgbVel === 1 ? t("slow") : (root.rgbVel === 3 ? t("fast") : t("medium"))
                                font.pointSize: 9; font.bold: true
                            }
                        }
                        PlasmaComponents.Slider {
                            Layout.fillWidth: true
                            from: 1; to: 3; stepSize: 1
                            value: root.rgbVel
                            onMoved: root.rgbVel = value
                            onPressedChanged: if (!pressed) root.aplicarRgb()
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            PlasmaComponents.Label { text: t("slow"); font.pointSize: 7.5; opacity: 0.7; Layout.fillWidth: true }
                            PlasmaComponents.Label { text: t("fast"); font.pointSize: 7.5; opacity: 0.7 }
                        }
                    }


                    // Controles de color (solo visibles en modo Fijo)
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.rgbModo === "fijo" || root.rgbModo === "respiracion" || root.rgbModo === "pulso"
                        enabled: root.rgbBrillo > 0
                        opacity: root.rgbBrillo > 0 ? 1.0 : 0.45
                        spacing: Kirigami.Units.smallSpacing

                        Kirigami.Separator { Layout.fillWidth: true }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Repeater {
                                model: Array(
                                    { r: 255, g: 0, b: 0 }, //Rojo
                                    { r: 0, g: 210, b: 255 }, //Cian
                                    { r: 165, g: 40, b: 255 }, //Morado / Violeta
                                    { r: 0, g: 255, b: 0  }, //Verde
                                    { r: 255, g: 110, b: 0 }, //Naranja
                                    { r: 255, g: 165, b: 0 }, //Amarillo
                                    { r: 255, g: 255, b: 255 } //Blanco
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

