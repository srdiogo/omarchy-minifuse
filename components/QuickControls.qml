pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons
import qs.Ui as Ui
import "." as Components

Rectangle {
    id: root
    property var backend: null
    signal dismissRequested()
    color: Color.popups.background
    implicitWidth: Style.space(1080)
    implicitHeight: content.implicitHeight + Style.spacing.huge * 2
    readonly property var model: backend ? backend.model : ({status: "MiniFuse service unavailable", message: "", mixes: [], inputs: {}})
    readonly property var selected: model.mixes.find(m => m.mix === model.selected) || null
    readonly property bool mixWritable: !!selected && selected.route === "mix" && !!model.can_write
    readonly property var meters: model.meters || null
    readonly property bool metersAvailable: !!meters
    readonly property bool nativeLoopback: model.layout === "loopback_mixer"
    readonly property bool hasMixer: !model.layout || model.layout === "mf4_mixer" || nativeLoopback

    function layoutSnapshot() {
        return {width: width, height: height, contentHeight: content.implicitHeight,
                masterX: master.x, masterY: master.y, masterHeight: master.height,
                sourceCount: sourceStrips.count, footerY: footer.y,
                sourceAreaWidth: sourceViewport.width,
                sourceContentWidth: strips.implicitWidth,
                sourceContentHeight: strips.implicitHeight,
                routeButtons: Array.from({length: nativeRoutes.count}, (_, i) => nativeRoutes.itemAt(i)),
                strips: Array.from({length: sourceStrips.count}, (_, i) => sourceStrips.itemAt(i))}
    }
    function dismiss() { dismissRequested() }
    function focusInitial() { if (tabs.count) tabs.itemAt(0)?.forceActiveFocus() }
    function send(value) { if (backend) backend.command(value) }
    function mixLabel(value) { return ({out12: "Outputs 1–2", out34: "Outputs 3–4", loopback: "Loopback"})[value] || value }
    function mixSubtitle(value) { return ({out12: "Monitor · Phones 1", out34: "Monitor · Phones 2", loopback: "Recording return"})[value] || "" }
    function routeLabel(value) { return ({mix: "Custom mix", usb12: "USB 1–2", usb34: "USB 3–4", usb56: "USB 5–6", out12: "Outputs 1–2", out34: "Outputs 3–4"})[value] || value }
    function sourceLabel(value) { return ({usb12: "USB 1–2", usb34: "USB 3–4", usb56: "USB 5–6"})[value] || value.replace(/^analog/, "Analog ").replace(/^usb/, "USB ") }
    function sourceMeter(source) {
        if (!meters) return []
        if (nativeLoopback) return source.startsWith("analog") ? [meters.inputs[Number(source.slice(6)) - 1]] : []
        const names = ["analog1", "analog2", "analog3", "analog4", "usb1", "usb2", "usb3", "usb4", "usb5", "usb6"]
        const index = names.indexOf(source)
        return index >= 0 ? [meters.sources[index]] : []
    }
    function editSource(source, action, value, finish) {
        const command = {action: action, source: source, value: value}
        if (action === "level" || action === "pan") command.finish = finish
        send(command)
    }

    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.spacing.huge }
        spacing: Style.spacing.lg
        Keys.onEscapePressed: root.dismiss()

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.spacing.xs
                Components.Label { text: root.model.model_name || "MiniFuse"; font.pixelSize: Style.font.heading; font.bold: true; Layout.fillWidth: true }
                Components.Label { text: root.nativeLoopback ? "HARDWARE LOOPBACK MIXER" : root.hasMixer ? "HARDWARE MIXER" : "INPUTS & MONITORING"; color: Color.muted; font.pixelSize: Style.font.caption; Layout.fillWidth: true }
            }
            Rectangle { implicitWidth: Style.space(6); implicitHeight: implicitWidth; radius: width / 2; color: root.model.connected ? Color.accent : Color.muted }
            Components.Label { text: root.model.connected ? "CONNECTED" : "OFFLINE"; font.pixelSize: Style.font.caption; color: Color.muted }
            Ui.Button { text: "Close"; focusable: true; onClicked: root.dismiss() }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Style.normalBorderFor(Color.foreground, Color.accent) }
        RowLayout {
            Layout.fillWidth: true
            spacing: Style.spacing.sm
            visible: root.hasMixer
            Repeater {
                id: tabs
                model: root.model.mixes.length
                Ui.Button {
                    required property int index
                    readonly property var mix: root.model.mixes[index] || null
                    text: mix ? root.mixLabel(mix.mix) : ""
                    selected: !!mix && root.model.selected === mix.mix
                    bordered: true
                    focusable: true
                    Layout.fillWidth: true
                    horizontalPadding: Style.spacing.sm
                    enabled: !!mix && !root.model.busy
                    onClicked: if (mix) root.send({action: "select_mix", value: mix.mix})
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Style.spacing.lg
            visible: root.hasMixer
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.spacing.xs
                Components.Label { text: root.selected ? root.mixSubtitle(root.selected.mix) : "No supported mixer connected"; font.bold: true; Layout.fillWidth: true }
                Components.Label {
                    text: root.selected && root.selected.route !== "mix" ? "Direct route · custom mix bypassed" : "INPUTS & COMPUTER PLAYBACK"
                    color: Color.muted; font.pixelSize: Style.font.caption; Layout.fillWidth: true
                }
            }
            Ui.Dropdown {
                visible: !root.nativeLoopback
                label: "Route"
                Layout.preferredWidth: Math.min(Style.space(195), root.width * 0.4)
                value: root.selected ? root.selected.route : ""
                options: root.selected ? root.selected.routes.map(r => ({value: r, label: root.routeLabel(r)})) : []
                enabled: !!root.selected && !!root.model.can_write && !root.model.busy
                onChanged: function(value) { root.send({action: "route", value: value}) }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: master.implicitHeight
            visible: root.hasMixer
            spacing: Style.spacing.lg
            Controls.ScrollView {
                id: sourceViewport
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: strips.implicitWidth
                contentHeight: strips.implicitHeight
                clip: true
                Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AlwaysOff
                Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AsNeeded
                Components.Label {
                    visible: !root.selected
                    x: Style.spacing.huge
                    y: Style.space(130)
                    width: Math.max(0, sourceViewport.availableWidth - Style.spacing.huge * 2)
                    text: "Connect a supported MiniFuse and start mf-service to see its hardware mixer."
                    horizontalAlignment: Text.AlignHCenter
                    color: Color.muted
                }
                Row {
                    id: strips
                    spacing: Style.spacing.xs
                    Repeater {
                        id: sourceStrips
                        model: root.selected ? root.selected.channels.length : 0
                        Components.ChannelStrip {
                            required property int index
                            width: {
                                const count = Math.max(1, root.selected ? root.selected.channels.length : 0)
                                return Math.max(Style.space(100), (sourceViewport.availableWidth - strips.spacing * (count - 1)) / count)
                            }
                            channel: root.selected ? root.selected.channels[index] : null
                            source: channel ? channel.source : ""
                            title: root.sourceLabel(source)
                            subtitle: channel && !channel.included ? "OUTSIDE MIX" : source.startsWith("analog") ? "INPUT" : "PLAYBACK"
                            writable: root.mixWritable
                            controlState: root.model
                            meterLevels: root.sourceMeter(source)
                            metersAvailable: !!root.meters && (!root.nativeLoopback || source.startsWith("analog"))
                            onEdit: function(action, value, finish) { root.editSource(source, action, value, finish) }
                        }
                    }
                }
            }
            Rectangle { implicitWidth: 1; Layout.fillHeight: true; color: Style.normalBorderFor(Color.foreground, Color.accent) }
            Components.ChannelStrip {
                id: master
                master: true
                title: "Mix master"
                subtitle: root.selected ? root.mixLabel(root.selected.mix) : "Unavailable"
                channel: root.selected
                writable: root.mixWritable
                controlState: root.model
                meterLevels: root.nativeLoopback ? (root.meters ? root.meters.loopback : []) : root.meters && root.selected ? root.meters.mixes[["out12", "out34", "loopback"].indexOf(root.selected.mix)] || [] : []
                metersAvailable: !!root.meters
                onEdit: function(action, value, finish) { root.send({action: action, value: value, finish: finish}) }
            }
        }
        Flow {
            Layout.fillWidth: true
            visible: root.nativeLoopback
            spacing: Style.spacing.sm
            Repeater {
                id: nativeRoutes
                model: [{field: "enabled", label: "Loopback"}, {field: "usb12", label: "Also record on USB 1–2"}, {field: "monitor", label: "Monitor mix"}]
                Components.StateButton {
                    required property var modelData
                    implicitWidth: contentItem.implicitWidth + Style.spacing.lg * 2
                    text: modelData.label
                    tooltipText: modelData.label
                    active: !!root.model.loopback && root.model.loopback[modelData.field] === true
                    enabled: !!root.model.can_write && !root.model.busy
                    onClicked: root.send({action: "loopback_routing", field: modelData.field, value: !active})
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.nativeLoopback && root.model.profile && root.model.profile.id === "mf2_otg"
            Ui.Dropdown {
                label: "Main → OTG"
                value: root.model.otg ? String(root.model.otg.main_to_otg) : "0"
                options: [{value: "0", label: "OTG 3–4"}, {value: "1", label: "Output 1–2"}]
                enabled: !!root.model.can_write && !root.model.busy
                onChanged: function(value) { root.send({action: "otg_routing", field: "main_to_otg", value: Number(value)}) }
            }
            Components.StateButton {
                implicitWidth: contentItem.implicitWidth + Style.spacing.lg * 2
                text: "Monitor OTG"
                tooltipText: "Use OTG playback as the monitoring source"
                active: !!root.model.otg && root.model.otg.otg_to_monitor === true
                enabled: !!root.model.can_write && !root.model.busy
                onClicked: root.send({action: "otg_routing", field: "otg_to_monitor", value: !active})
            }
            Ui.Dropdown {
                label: "LED meters"
                value: root.model.otg ? String(root.model.otg.meter_source) : "0"
                options: ["Monitor out", "OTG in", "OTG out", "Computer out"].map((label, index) => ({value: String(index), label: label}))
                enabled: !!root.model.can_write && !root.model.busy
                onChanged: function(value) { root.send({action: "otg_routing", field: "meter_source", value: Number(value)}) }
            }
            Components.Label { text: "OTG in"; color: Color.muted; font.pixelSize: Style.font.caption }
            Repeater {
                model: 2
                Components.SignalMeter {
                    required property int index
                    Layout.preferredHeight: Style.space(28)
                    Layout.preferredWidth: Style.space(6)
                    available: !!root.meters
                    level: root.meters && root.meters.otg ? root.meters.otg[index] : null
                }
            }
            Item { Layout.fillWidth: true }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Style.normalBorderFor(Color.foreground, Color.accent) }
        Components.Label {
            visible: !!root.model.layout && root.model.layout !== "mf4_mixer"
            Layout.fillWidth: true
            text: root.nativeLoopback ? "Experimental hardware loopback · firmware " + ((root.model.firmware || {}).version || "unknown") + " · hardware acceptance pending" : root.model.layout === "initialization" ? "Initialization USB mode · audio controls unavailable" : "Experimental model support · hardware validation pending. Input indicators are read-only here; use MiniFuse Control for guided switch tests."
            color: Color.muted
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Style.spacing.sm
            Repeater {
                model: root.model.input_controls || [{target: "inst1", label: "INST 1"}, {target: "inst2", label: "INST 2"}, {target: "phantom_power", label: "+48 V"}]
                Rectangle {
                    required property var modelData
                    readonly property var switchValue: root.model.inputs ? root.model.inputs[modelData.target] : undefined
                    implicitWidth: indicator.implicitWidth + Style.spacing.lg * 2
                    implicitHeight: Style.space(28)
                    color: switchValue === true ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
                    border.width: 1
                    border.color: switchValue === true ? Color.accent : Style.normalBorderFor(Color.foreground, Color.accent)
                    radius: Style.cornerRadius
                    Components.Label {
                        id: indicator
                        anchors.centerIn: parent
                        text: parent.modelData.label + " · " + (parent.switchValue === undefined ? "—" : parent.switchValue ? "ON" : "OFF")
                        color: parent.switchValue === true ? Color.accent : Color.muted
                        font.pixelSize: Style.font.caption
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Components.Label { visible: (!root.model.layout || root.model.layout === "mf4_mixer") && root.width > Style.space(700); text: "dB = mix gain · meters = dBFS"; font.pixelSize: Style.font.caption; color: Color.muted }
        }
        RowLayout {
            id: footer
            Layout.fillWidth: true
            spacing: Style.spacing.lg
            Components.Label {
                id: feedback
                Layout.fillWidth: true
                Layout.preferredHeight: Style.space(40)
                Layout.minimumHeight: Style.space(40)
                Layout.maximumHeight: Style.space(40)
                maximumLineCount: 2
                elide: Text.ElideRight
                color: root.model.uncertain ? Color.urgent : Color.muted
                font.pixelSize: Style.font.caption
                text: root.model.message || (root.model.busy ? "Adjusting · waiting for device readback" : root.model.connected ? "Live device state · " + (root.meters ? "signal meters active" : "signal meters unavailable") : root.model.status)
            }
            Controls.ToolTip {
                visible: feedbackHover.hovered && !!root.model.message
                text: root.model.message || ""
                delay: 500
                font.family: Style.font.family
            }
            HoverHandler { id: feedbackHover; parent: feedback }
            Ui.Button {
                visible: !!root.model.can_acknowledge
                text: "Acknowledge state"
                focusable: true
                onClicked: root.send({action: "acknowledge"})
            }
            Ui.Button {
                objectName: "open-full-mixer"
                text: root.model.layout && root.model.layout !== "mf4_mixer" ? "Open controls ↗" : "Open full mixer ↗"
                bordered: true
                focusable: true
                onClicked: { root.send({action: "open_app"}); root.dismiss() }
            }
        }
    }
}
