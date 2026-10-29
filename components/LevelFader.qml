import QtQuick
import QtQuick.Controls
import qs.Commons

Slider {
    id: root
    property real minimumDb: -60
    property real maximumDb: 12
    from: minimumDb - 1
    to: maximumDb
    stepSize: 0.5
    orientation: Qt.Vertical
    implicitWidth: Style.space(38)
    implicitHeight: Style.space(220)
    leftPadding: Style.space(8)
    rightPadding: Style.space(8)
    topPadding: Style.space(8)
    bottomPadding: Style.space(8)
    Accessible.name: "Mix level"
    background: Rectangle {
        x: root.leftPadding + root.availableWidth / 2 - width / 2
        y: root.topPadding
        width: Style.space(4)
        height: root.availableHeight
        radius: width / 2
        color: Style.normalFillFor(Color.foreground, Color.accent)
        border.width: 1
        border.color: Style.normalBorderFor(Color.foreground, Color.accent)
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: root.position * parent.height
            color: root.enabled ? Color.accent : Color.muted
            radius: parent.radius
            opacity: 0.8
        }
    }
    handle: Rectangle {
        x: root.leftPadding + root.availableWidth / 2 - width / 2
        y: root.topPadding + root.visualPosition * (root.availableHeight - height)
        width: Style.space(25)
        height: Style.space(9)
        radius: Style.space(2)
        color: root.enabled ? Color.foreground : Color.muted
        border.width: root.activeFocus ? 2 : 0
        border.color: Color.accent
        Rectangle {
            anchors.centerIn: parent
            width: parent.width - Style.space(8)
            height: 1
            color: Color.popups.background
        }
    }
}
