import QtQuick
import qs.Commons

Item {
    id: root
    property var level: null
    property bool available: false
    readonly property real fraction: available && typeof level === "number" ? Math.max(0, Math.min(1, (level + 60) / 60)) : 0
    implicitWidth: Style.space(6)
    implicitHeight: Style.space(220)
    Accessible.name: "Signal meter"
    Accessible.description: !available ? "Unavailable" : level === null ? "Silence" : Number(level).toFixed(1) + " dBFS"
    Rectangle {
        anchors.fill: parent
        color: Style.normalFillFor(Color.foreground, Color.accent)
        border.width: 1
        border.color: Style.normalBorderFor(Color.foreground, Color.accent)
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: root.fraction * parent.height
            color: root.level !== null && root.level >= -1 ? Color.urgent : Color.accent
            Behavior on height { NumberAnimation { duration: 65 } }
        }
    }
}
