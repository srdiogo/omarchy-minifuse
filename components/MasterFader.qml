import QtQuick
import QtQuick.Controls
import qs.Commons

Slider {
    id: root
    from: -65
    to: 0
    stepSize: 0.5
    implicitHeight: Style.spacing.controlHeight
    Accessible.name: "MiniFuse mix master level"
    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth
        height: Style.space(4)
        radius: height / 2
        color: Color.muted
        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: height / 2
            color: root.enabled ? Color.accent : Color.muted
        }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: Style.space(16)
        height: width
        radius: width / 2
        color: root.enabled ? Color.foreground : Color.muted
        border.width: root.activeFocus ? Style.space(2) : 0
        border.color: Color.accent
    }
}
