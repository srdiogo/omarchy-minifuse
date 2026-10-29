import QtQuick
import Quickshell
import qs.Commons

Item {
    id: root
    property var bar: null
    property string moduleName: "srdiogo.minifuse"
    property var settings: ({})
    readonly property var backend: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
    readonly property var model: backend ? backend.model : ({connected: false, status: "MiniFuse service entry unavailable"})
    implicitWidth: bar && bar.vertical ? bar.barSize : label.implicitWidth + Style.space(20)
    implicitHeight: bar ? bar.barSize : Style.space(32)
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: "Toggle MiniFuse mixer panel"
    function open() {
        if (bar && bar.shell)
            bar.shell.toggle(moduleName, JSON.stringify({screen: root.QsWindow.window ? root.QsWindow.window.screen.name : "", position: bar.position, barSize: bar.barSize}))
    }
    Keys.onReturnPressed: open()
    Keys.onEnterPressed: open()
    Keys.onSpacePressed: open()
    Rectangle {
        anchors.fill: parent
        anchors.margins: Style.space(3)
        radius: Style.cornerRadius
        color: root.activeFocus || mouse.containsMouse ? Style.hoverFillFor(Color.foreground, Color.accent) : "transparent"
    }
    Text {
        id: label
        anchors.centerIn: parent
        textFormat: Text.PlainText
        text: "MF"
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.bold: true
        color: root.model.uncertain ? Color.urgent : (root.model.connected ? Color.foreground : Color.muted)
    }
    Rectangle {
        width: Style.space(4)
        height: width
        radius: width / 2
        anchors.bottom: label.top
        anchors.horizontalCenter: label.horizontalCenter
        color: root.model.can_write ? Color.accent : Color.muted
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.open()
        onEntered: {
            if (root.bar && typeof root.bar.showTooltip === "function")
                root.bar.showTooltip(root, "MiniFuse · " + root.model.status)
        }
        onExited: {
            if (root.bar && typeof root.bar.hideTooltip === "function")
                root.bar.hideTooltip(root)
        }
    }
}
