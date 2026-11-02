import QtQuick
import QtQuick.Controls
import qs.Commons as Commons

Slider {
    id: root
    property real minimumDb: -60
    property real maximumDb: 12
    from: minimumDb - 1
    to: maximumDb
    stepSize: 0.5
    orientation: Qt.Vertical
    implicitWidth: Commons.Style.space(38)
    implicitHeight: Commons.Style.space(220)
    leftPadding: Commons.Style.space(8)
    rightPadding: Commons.Style.space(8)
    topPadding: Commons.Style.space(8)
    bottomPadding: Commons.Style.space(8)
    Accessible.name: "Mix level"
    background: Rectangle {
        x: root.leftPadding + root.availableWidth / 2 - width / 2
        y: root.topPadding
        width: Commons.Style.space(4)
        height: root.availableHeight
        radius: width / 2
        color: Commons.Style.normalFillFor(Commons.Color.foreground, Commons.Color.accent)
        border.width: 1
        border.color: Commons.Style.normalBorderFor(Commons.Color.foreground, Commons.Color.accent)
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: root.position * parent.height
            color: root.enabled ? Commons.Color.accent : Commons.Color.muted
            radius: parent.radius
            opacity: 0.8
        }
    }
    handle: Rectangle {
        x: root.leftPadding + root.availableWidth / 2 - width / 2
        y: root.topPadding + root.visualPosition * (root.availableHeight - height)
        width: Commons.Style.space(25)
        height: Commons.Style.space(9)
        radius: Commons.Style.space(2)
        color: root.enabled ? Commons.Color.foreground : Commons.Color.muted
        border.width: root.activeFocus ? 2 : 0
        border.color: Commons.Color.accent
        Rectangle {
            anchors.centerIn: parent
            width: parent.width - Commons.Style.space(8)
            height: 1
            color: Commons.Color.popups.background
        }
    }
}
