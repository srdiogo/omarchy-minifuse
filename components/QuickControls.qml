import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui as Ui
import "." as Components

Rectangle {
    id: root
    property var backend: null
    signal dismissRequested()
    color: Color.popups.background
    implicitWidth: Style.space(420)
    implicitHeight: content.implicitHeight + Style.spacing.huge * 2
    readonly property var model: backend ? backend.model : ({status: "MiniFuse service entry unavailable", message: "", mixes: [], inputs: {}})
    readonly property var selected: model.mixes.find(m => m.mix === model.selected) || null
    property string selectedSource: "analog1"
    readonly property var channel: selected ? selected.channels.find(c => c.source === selectedSource) : null

    function dismiss() { dismissRequested() }
    function focusInitial() { mixChoice.forceActiveFocus() }
    function send(value) { if (backend) backend.command(value) }
    function mixLabel(value) {
        return ({out12: "Outputs 1–2", out34: "Outputs 3–4", loopback: "Loopback"})[value] || value
    }
    function levelLabel(value) { return value === null ? "−∞ dB" : Number(value).toFixed(1) + " dB" }
    function moveMaster(finish) {
        send({action: "master", value: master.value < -64.5 ? null : Math.max(-64, master.value), finish: finish})
    }

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Style.spacing.huge
        spacing: Style.spacing.lg
        Keys.onEscapePressed: root.dismiss()

        RowLayout {
            Layout.fillWidth: true
            Components.Label {
                text: "MiniFuse"
                font.pixelSize: Style.font.heading
                font.bold: true
                Layout.fillWidth: true
            }
            Ui.Button { text: "Close"; focusable: true; onClicked: root.dismiss() }
        }
        Components.Label { text: root.model.status; Layout.fillWidth: true }
        Ui.Dropdown {
            id: mixChoice
            label: "Hardware mix"
            Layout.fillWidth: true
            value: root.model.selected || ""
            options: root.model.mixes.map(m => ({value: m.mix, label: root.mixLabel(m.mix)}))
            enabled: !!root.selected && !root.model.busy
            onChanged: function(value) { root.send({action: "select_mix", value: value}) }
        }
        RowLayout {
            Layout.fillWidth: true
            Components.Label { text: "Master"; Layout.fillWidth: true }
            Components.Label {
                text: master.pressed || root.model.live ? root.levelLabel(master.value < -64.5 ? null : master.value) : (root.selected ? root.levelLabel(root.selected.master_db) : "Unavailable")
                font.bold: true
                horizontalAlignment: Text.AlignRight
                Layout.minimumWidth: Style.space(100)
            }
        }
        Components.MasterFader {
            id: master
            Layout.fillWidth: true
            enabled: !!root.selected && root.selected.route === "mix" && !!root.model.can_write && (!root.model.busy || !!root.model.live)
            onMoved: root.moveMaster(!pressed)
            onPressedChanged: if (!pressed && enabled) root.moveMaster(true)
        }
        Binding {
            target: master
            property: "value"
            value: root.selected && root.selected.master_db !== null ? root.selected.master_db : -65
            when: !master.pressed && !root.model.live
            restoreMode: Binding.RestoreNone
        }
        Components.Label {
            Layout.fillWidth: true
            font.pixelSize: Style.font.caption
            text: root.selected && root.selected.route !== "mix" ? "This destination bypasses its custom mix. Its master does not control the selected route." : "Configured hardware mix level. Separate from host volume and signal meters."
        }
        Ui.Dropdown {
            label: "Destination route"
            Layout.fillWidth: true
            value: root.selected ? root.selected.route : ""
            options: root.selected ? root.selected.routes.map(r => ({value: r, label: root.mixLabel(r)})) : []
            enabled: !!root.model.can_write && !root.model.busy
            onChanged: function(value) { root.send({action: "route", value: value}) }
        }
        RowLayout {
            Layout.fillWidth: true
            Ui.Dropdown {
                label: "Source"
                Layout.fillWidth: true
                value: root.selectedSource
                options: root.selected ? root.selected.channels.map(c => c.source) : []
                enabled: !!root.selected && !root.model.busy
                onChanged: function(value) { root.selectedSource = value }
            }
            Ui.Button {
                text: root.channel && root.channel.mute ? "Unmute source" : "Mute source"
                selected: !!root.channel && root.channel.mute
                focusable: true
                enabled: !!root.channel && !!root.model.can_write && !root.model.busy
                Layout.alignment: Qt.AlignBottom
                onClicked: root.send({action: "mute", source: root.selectedSource, value: !root.channel.mute})
            }
        }
        Components.Label {
            visible: typeof root.model.inputs.inst1 === "boolean"
            Layout.fillWidth: true
            font.pixelSize: Style.font.caption
            text: "Input indicators · INST 1 " + (root.model.inputs.inst1 ? "on" : "off") + " · INST 2 " + (root.model.inputs.inst2 ? "on" : "off") + " · +48 V " + (root.model.inputs.phantom_power ? "on" : "off")
        }
        // Reserve a status slot so pointer interaction never moves the controls.
        Components.Label {
            Layout.fillWidth: true
            Layout.minimumHeight: font.pixelSize * 4
            Layout.maximumHeight: font.pixelSize * 4
            maximumLineCount: 3
            elide: Text.ElideRight
            color: root.model.uncertain ? Color.urgent : Color.muted
            text: root.model.message || " "
        }
        Ui.Button {
            visible: !!root.model.can_acknowledge
            text: "Acknowledge inspected device state"
            focusable: true
            Layout.fillWidth: true
            onClicked: root.send({action: "acknowledge"})
        }
        Ui.Button {
            text: "Open full mixer & presets"
            focusable: true
            Layout.fillWidth: true
            onClicked: root.send({action: "open_app"})
        }
    }
}
