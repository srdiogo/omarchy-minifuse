pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons as Commons
import "." as Components

Rectangle {
    id: root
    property string source: ""
    property string title: ""
    property string subtitle: ""
    property var channel: null
    property var meterLevels: []
    property bool metersAvailable: false
    property bool master: false
    property bool writable: false
    property var controlState: ({busy: false, live_target: null})
    readonly property bool busy: !!controlState.busy
    readonly property var liveTarget: controlState.live_target || null
    signal edit(string action, var value, bool finish)
    readonly property bool included: master || !!channel && !!channel.included
    readonly property bool ownLevel: !!liveTarget && liveTarget.kind === (master ? "master_level" : "channel_level") && (master || liveTarget.source === source)
    readonly property bool ownPan: !!liveTarget && liveTarget.kind === "channel_pan" && liveTarget.source === source
    readonly property real minimumDb: master ? -64 : -60
    readonly property real maximumDb: master ? 0 : 12
    readonly property var confirmedDb: channel ? (master ? channel.master_db : channel.level_db) : null
    readonly property var ticks: master ? [0, -12, -24, -36, -48, -64] : [12, 0, -12, -24, -36, -48, -60]
    implicitWidth: Commons.Style.space(master ? 138 : 100)
    implicitHeight: body.implicitHeight + Commons.Style.spacing.lg * 2
    color: master ? Commons.Style.normalFillFor(Commons.Color.foreground, Commons.Color.accent) : "transparent"
    border.color: master ? Commons.Style.normalBorderFor(Commons.Color.foreground, Commons.Color.accent) : "transparent"
    border.width: master ? 1 : 0
    radius: Commons.Style.cornerRadius

    function controlAllowed(kind) {
        const state = controlState
        const target = state.live_target
        const own = !!target && target.kind === kind && (master || target.source === source)
        return !state.busy || own
    }
    function levelText(value) { return value === null ? "−∞ dB" : Number(value).toFixed(1) + " dB" }
    function sendLevel(finish) {
        edit(master ? "master" : "level", level.value < minimumDb - 0.5 ? null : Math.max(minimumDb, level.value), finish)
    }
    function sendPan(finish) { edit("pan", pan.value, finish) }

    // Slider.moved can precede pressedChanged on the initial pointer press.
    // Dispatch after that event; release cancels the deferred sample and flushes.
    Timer {
        id: levelDispatch
        interval: 0
        onTriggered: if (level.enabled) root.sendLevel(!level.pressed)
    }
    Timer {
        id: panDispatch
        interval: 0
        onTriggered: if (pan.enabled) root.sendPan(!pan.pressed)
    }

    ColumnLayout {
        id: body
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Commons.Style.spacing.lg }
        spacing: Commons.Style.spacing.sm
        opacity: root.included ? 1 : 0.45
        Components.Label {
            text: root.title
            font.bold: true
            wrapMode: Text.NoWrap
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Layout.preferredHeight: Commons.Style.space(22)
        }
        Components.Label {
            text: root.subtitle
            color: Commons.Color.muted
            font.pixelSize: Commons.Style.font.caption
            wrapMode: Text.NoWrap
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Layout.preferredHeight: Commons.Style.space(18)
        }
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Commons.Style.space(47)
            Components.Label {
                visible: root.master
                anchors.centerIn: parent
                text: "MASTER"
                font.pixelSize: Commons.Style.font.caption
                color: Commons.Color.accent
            }
            ColumnLayout {
                visible: !root.master
                anchors.fill: parent
                spacing: 0
                Components.Label {
                    text: {
                        const value = pan.pressed || root.ownPan ? pan.value : root.channel ? root.channel.pan : null
                        if (root.channel && root.channel.pan_available === false) return root.channel.level_mixed ? "STEREO · MIXED" : "STEREO"
                        return value === null ? "PAN —" : Math.abs(value - 0.5) < 0.01 ? "CENTER" : (value < 0.5 ? "L " : "R ") + Math.round(Math.abs(value - 0.5) * 200)
                    }
                    color: Commons.Color.muted
                    font.pixelSize: Commons.Style.font.caption
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                }
                Components.MasterFader {
                    id: pan
                    visible: !root.channel || root.channel.pan_available !== false
                    objectName: "pan-" + root.source
                    from: 0; to: 1; stepSize: 0.01
                    Layout.fillWidth: true
                    Layout.preferredHeight: Commons.Style.space(24)
                    enabled: !root.master && root.included && root.writable && (!root.channel || root.channel.pan_available !== false) && root.controlAllowed("channel_pan")
                    Accessible.name: root.title + " pan"
                    onMoved: panDispatch.restart()
                    onPressedChanged: if (!pressed) { panDispatch.stop(); if (enabled) root.sendPan(true) }
                }
                Binding {
                    target: pan; property: "value"
                    value: root.channel && root.channel.pan !== null ? root.channel.pan : 0.5
                    when: !pan.pressed && !root.ownPan
                    restoreMode: Binding.RestoreNone
                }
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Commons.Style.space(30)
            RowLayout {
                anchors.fill: parent
                spacing: Commons.Style.spacing.xs
                visible: !root.master
                Components.StateButton {
                    objectName: "mute-" + root.source
                    text: root.channel && root.channel.mute_mixed ? "M·" : "M"
                    tooltipText: "Mute " + root.title
                    active: !!root.channel && !!root.channel.mute
                    Accessible.name: tooltipText
                    Layout.preferredWidth: Commons.Style.space(34)
                    Layout.fillWidth: true
                    enabled: root.included && root.writable && !root.busy
                    onClicked: root.edit("mute", !root.channel.mute, true)
                }
                Components.StateButton {
                    visible: !root.channel || root.channel.solo_available !== false
                    objectName: "solo-" + root.source
                    text: "S"
                    tooltipText: "Solo " + root.title
                    active: !!root.channel && !!root.channel.solo
                    Accessible.name: tooltipText
                    Layout.preferredWidth: Commons.Style.space(34)
                    Layout.fillWidth: true
                    enabled: !root.master && !!root.channel && root.included && root.writable && !root.busy && root.channel.solo_available !== false
                    onClicked: root.edit("solo", !root.channel.solo, true)
                }
            }
            Components.Label {
                visible: root.master
                anchors.centerIn: parent
                text: !root.channel ? "NO DEVICE" : root.channel.route !== "mix" ? "DIRECT ROUTE" : root.writable ? "CUSTOM MIX" : "READ ONLY"
                color: Commons.Color.muted
                font.pixelSize: Commons.Style.font.caption
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Commons.Style.space(220)
            Item {
                id: levelScale
                width: Commons.Style.space(25)
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom; topMargin: Commons.Style.space(8); bottomMargin: Commons.Style.space(8) }
                Repeater {
                    model: root.ticks.length
                    Components.Label {
                        required property int index
                        readonly property real db: root.ticks[index]
                        text: db > 0 ? "+" + db : db
                        color: Commons.Color.muted
                        font.pixelSize: Commons.Style.font.caption
                        width: levelScale.width
                        horizontalAlignment: Text.AlignRight
                        y: (root.maximumDb - db) / (root.maximumDb - root.minimumDb + 1) * (levelScale.height - Commons.Style.space(9)) - height / 2 + Commons.Style.space(4.5)
                    }
                }
            }
            Components.LevelFader {
                id: level
                objectName: root.master ? "master-fader" : "level-" + root.source
                anchors { left: levelScale.right; top: parent.top; bottom: parent.bottom }
                minimumDb: root.minimumDb
                maximumDb: root.maximumDb
                enabled: root.included && root.writable && root.controlAllowed(root.master ? "master_level" : "channel_level")
                Accessible.name: root.title + " level"
                onMoved: levelDispatch.restart()
                onPressedChanged: if (!pressed) { levelDispatch.stop(); if (enabled) root.sendLevel(true) }
            }
            Binding {
                target: level; property: "value"
                value: root.confirmedDb === null ? root.minimumDb - 1 : Math.max(root.minimumDb, Math.min(root.maximumDb, root.confirmedDb))
                when: !level.pressed && !root.ownLevel
                restoreMode: Binding.RestoreNone
            }
            Row {
                id: meterBank
                anchors { right: parent.right; top: parent.top; bottom: parent.bottom; topMargin: Commons.Style.space(8); bottomMargin: Commons.Style.space(8) }
                spacing: Commons.Style.space(2)
                Repeater {
                    model: root.master ? 2 : 1
                    Components.SignalMeter {
                        required property int index
                        height: meterBank.height
                        level: root.meterLevels[index] === undefined ? null : root.meterLevels[index]
                        available: root.metersAvailable
                    }
                }
            }
        }
        Components.Label {
            text: level.pressed || root.ownLevel ? root.levelText(level.value < root.minimumDb - 0.5 ? null : level.value) : root.channel ? root.levelText(root.confirmedDb) : "— dB"
            font.bold: true
            color: root.included ? Commons.Color.popups.text : Commons.Color.muted
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.NoWrap
            Layout.fillWidth: true
            Layout.preferredHeight: Commons.Style.space(24)
        }
    }
}
