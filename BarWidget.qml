import QtQuick
import Quickshell
import qs.Commons as Commons

Item {
    id: root
    property var bar: null
    property string moduleName: "srdiogo.minifuse"
    property var settings: ({})
    readonly property var backend: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
    readonly property var model: backend ? backend.model : ({connected: false, status: "MiniFuse service entry unavailable"})
    implicitWidth: bar && bar.vertical ? bar.barSize : label.implicitWidth + Commons.Style.space(20)
    implicitHeight: bar ? bar.barSize : Commons.Style.space(32)
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
        anchors.margins: Commons.Style.space(3)
        radius: Commons.Style.cornerRadius
        color: root.activeFocus || mouse.containsMouse ? Commons.Style.hoverFillFor(Commons.Color.foreground, Commons.Color.accent) : "transparent"
    }
    Text {
        id: label
        anchors.centerIn: parent
        textFormat: Text.PlainText
        text: "MF"
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        font.bold: true
        color: root.model.uncertain ? Commons.Color.urgent : (root.model.connected ? Commons.Color.foreground : Commons.Color.muted)
    }
    Rectangle {
        width: Commons.Style.space(4)
        height: width
        radius: width / 2
        anchors.bottom: label.top
        anchors.horizontalCenter: label.horizontalCenter
        color: root.model.can_write ? Commons.Color.accent : Commons.Color.muted
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
