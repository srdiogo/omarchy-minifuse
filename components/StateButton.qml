import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.AbstractButton {
    id: root
    property bool active: false
    property string tooltipText: ""
    implicitWidth: Style.space(34)
    implicitHeight: Style.space(30)
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    checked: active
    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true
    Accessible.checked: active
    contentItem: Text {
        text: root.text
        textFormat: Text.PlainText
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.bold: root.active
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: root.active ? Color.accent : Color.muted
    }
    background: Rectangle {
        radius: Style.cornerRadius
        color: root.active ? Style.selectedFillFor(Color.foreground, Color.accent)
             : root.down ? Style.pressedFillFor(Color.foreground, Color.accent)
             : root.hovered ? Style.hoverFillFor(Color.foreground, Color.accent) : "transparent"
        border.width: root.activeFocus ? Style.space(2) : 1
        border.color: root.active ? Color.accent : root.activeFocus ? Color.foreground : Style.normalBorderFor(Color.foreground, Color.accent)
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Style.space(4) }
            height: Style.space(2)
            color: Color.accent
            visible: root.active
        }
    }
    Controls.ToolTip.visible: hovered && tooltipText !== ""
    Controls.ToolTip.text: tooltipText + (active ? " · on" : " · off")
    Controls.ToolTip.delay: 400
}
