pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Commons
import "components" as Components

Item {
    id: root
    property var shell: null
    property var manifest: null
    property var service: null
    property bool opened: false
    property string screenName: ""
    property string position: "top"
    property real barSize: Style.bar.sizeHorizontal
    readonly property var backend: service || (shell ? shell.serviceFor("srdiogo.minifuse") : null)
    readonly property var targetScreen: Quickshell.screens.find(s => s.name === screenName) || Quickshell.screens[0]

    onBackendChanged: if (opened && backend) backend.command({action: "watch", value: true})

    function open(payloadJson) {
        let payload = {}
        try { payload = JSON.parse(payloadJson || "{}") } catch (error) {}
        const focused = Hyprland.focusedMonitor
        screenName = payload && typeof payload.screen === "string" ? payload.screen : (focused ? focused.name : "")
        const configured = shell && shell.barConfig ? shell.barConfig.position : "top"
        const requested = payload && payload.position ? payload.position : configured
        position = ["top", "bottom", "left", "right"].includes(requested) ? requested : "top"
        const size = payload && payload.barSize
        barSize = typeof size === "number" && size >= 16 && size <= 512 ? size : (position === "left" || position === "right" ? Style.bar.sizeVertical : Style.bar.sizeHorizontal)
        if (backend) backend.command({action: "watch", value: true})
        opened = true
        Qt.callLater(function() { if (surface.item) surface.item.focusInitial() })
    }
    function close() {
        if (backend) backend.command({action: "watch", value: false})
        opened = false
    }
    function dismiss() {
        if (!opened) return
        if (shell) shell.hide("srdiogo.minifuse")
        else close()
    }

    Loader {
        id: surface
        active: root.opened
        sourceComponent: Component {
            PanelWindow {
                id: window
                screen: root.targetScreen
                visible: true
                color: Color.popups.background
                exclusiveZone: 0
                WlrLayershell.namespace: "srdiogo.minifuse"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
                readonly property real gap: Style.spacing.lg
                implicitWidth: Math.min(quick.implicitWidth, screen ? screen.width - gap * 2 - (root.position === "left" || root.position === "right" ? root.barSize : 0) : quick.implicitWidth)
                implicitHeight: Math.min(quick.implicitHeight, screen ? screen.height - gap * 2 - (root.position === "top" || root.position === "bottom" ? root.barSize : 0) : quick.implicitHeight)
                anchors {
                    top: root.position !== "bottom"
                    bottom: root.position === "bottom"
                    left: root.position === "left"
                    right: root.position !== "left"
                }
                // The runtime PanelWindow factory omits margin metadata.
                // qmllint disable unqualified
                margins.top: window.gap + (root.position === "top" ? root.barSize : 0)
                margins.bottom: window.gap + (root.position === "bottom" ? root.barSize : 0)
                margins.left: window.gap + (root.position === "left" ? root.barSize : 0)
                margins.right: window.gap + (root.position === "right" ? root.barSize : 0)
                // qmllint enable unqualified
                function focusInitial() { quick.focusInitial() }
                HyprlandFocusGrab {
                    id: focusGrab
                    active: false
                    windows: [window]
                    onCleared: root.dismiss()
                }
                Timer {
                    interval: 120
                    running: true
                    onTriggered: { window.focusInitial(); focusGrab.active = true }
                }
                Flickable {
                    anchors.fill: parent
                    contentWidth: width
                    contentHeight: quick.implicitHeight
                    clip: true
                    Controls.ScrollBar.vertical: Controls.ScrollBar {}
                    Components.QuickControls {
                        id: quick
                        width: parent.width
                        backend: root.backend
                        onDismissRequested: root.dismiss()
                    }
                }
            }
        }
    }
}
