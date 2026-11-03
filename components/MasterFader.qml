import QtQuick
import QtQuick.Controls
import qs.Commons as Commons

Slider {
    id: root
    from: -65
    to: 0
    stepSize: 0.5
    implicitHeight: Commons.Style.spacing.controlHeight
    Accessible.name: "MiniFuse mix master level"
    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth
        height: Commons.Style.space(4)
        radius: height / 2
        color: Commons.Color.muted
        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: height / 2
            color: root.enabled ? Commons.Color.accent : Commons.Color.muted
        }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: Commons.Style.space(16)
        height: width
        radius: width / 2
        color: root.enabled ? Commons.Color.foreground : Commons.Color.muted
        border.width: root.activeFocus ? Commons.Style.space(2) : 0
        border.color: Commons.Color.accent
    }
}
