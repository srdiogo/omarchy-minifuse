import QtQuick
import QtQuick.Controls as Controls
import qs.Commons as Commons

Controls.AbstractButton {
    id: root
    property bool active: false
    property string tooltipText: ""
    implicitWidth: Commons.Style.space(34)
    implicitHeight: Commons.Style.space(30)
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    checked: active
    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true
    Accessible.checked: active
    contentItem: Text {
        text: root.text
        textFormat: Text.PlainText
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        font.bold: root.active
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: root.active ? Commons.Color.accent : Commons.Color.muted
    }
    background: Rectangle {
        radius: Commons.Style.cornerRadius
        color: root.active ? Commons.Style.selectedFillFor(Commons.Color.foreground, Commons.Color.accent)
             : root.down ? Commons.Style.pressedFillFor(Commons.Color.foreground, Commons.Color.accent)
             : root.hovered ? Commons.Style.hoverFillFor(Commons.Color.foreground, Commons.Color.accent) : "transparent"
        border.width: root.activeFocus ? Commons.Style.space(2) : 1
        border.color: root.active ? Commons.Color.accent : root.activeFocus ? Commons.Color.foreground : Commons.Style.normalBorderFor(Commons.Color.foreground, Commons.Color.accent)
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Commons.Style.space(4) }
            height: Commons.Style.space(2)
            color: Commons.Color.accent
            visible: root.active
        }
    }
    Controls.ToolTip.visible: hovered && tooltipText !== ""
    Controls.ToolTip.text: tooltipText + (active ? " · on" : " · off")
    Controls.ToolTip.delay: 400
}
