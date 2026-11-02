import QtQuick
import qs.Commons as Commons

Item {
    id: root
    property var level: null
    property bool available: false
    readonly property real fraction: available && typeof level === "number" ? Math.max(0, Math.min(1, (level + 60) / 60)) : 0
    implicitWidth: Commons.Style.space(6)
    implicitHeight: Commons.Style.space(220)
    Accessible.name: "Signal meter"
    Accessible.description: !available ? "Unavailable" : level === null ? "Silence" : Number(level).toFixed(1) + " dBFS"
    Rectangle {
        anchors.fill: parent
        color: Commons.Style.normalFillFor(Commons.Color.foreground, Commons.Color.accent)
        border.width: 1
        border.color: Commons.Style.normalBorderFor(Commons.Color.foreground, Commons.Color.accent)
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: root.fraction * parent.height
            color: root.level !== null && root.level >= -1 ? Commons.Color.urgent : Commons.Color.accent
            Behavior on height { NumberAnimation { duration: 65 } }
        }
    }
}
