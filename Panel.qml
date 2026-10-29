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
                exclusionMode: ExclusionMode.Ignore
                WlrLayershell.namespace: "srdiogo.minifuse"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
                onBackingWindowVisibleChanged: if (backingWindowVisible) Qt.callLater(function() { window.focusInitial() })
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
                Flickable {
                    anchors.fill: parent
                    contentWidth: width
                    contentHeight: quick.implicitHeight
                    interactive: contentHeight > height + 1
                    boundsBehavior: Flickable.StopAtBounds
                    flickableDirection: Flickable.VerticalFlick
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

    function cardGeometry(screen) {
        if (!surface.item || !screen || !targetScreen || screen.name !== targetScreen.name)
            return Qt.rect(0, 0, 0, 0)
        const gap = Style.spacing.lg
        const width = surface.item.width
        const height = surface.item.height
        const x = position === "left" ? gap + barSize : screen.width - gap - width - (position === "right" ? barSize : 0)
        const y = position === "bottom" ? screen.height - gap - barSize - height : gap + (position === "top" ? barSize : 0)
        return Qt.rect(x, y, width, height)
    }

    Variants {
        model: root.opened ? Quickshell.screens : []
        delegate: Component {
            PanelWindow {
                id: backdrop
                required property var modelData
                readonly property rect card: root.cardGeometry(modelData)
                screen: modelData
                color: "transparent"
                exclusionMode: ExclusionMode.Ignore
                WlrLayershell.namespace: "srdiogo.minifuse.dismiss"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                anchors { top: true; bottom: true; left: true; right: true }
                mask: Region {
                    width: backdrop.width
                    height: backdrop.height
                    Region {
                        intersection: Intersection.Subtract
                        x: backdrop.card.x; y: backdrop.card.y
                        width: backdrop.card.width; height: backdrop.card.height
                    }
                    Region {
                        intersection: Intersection.Subtract
                        x: root.position === "right" ? backdrop.width - root.barSize : 0
                        y: root.position === "bottom" ? backdrop.height - root.barSize : 0
                        width: root.position === "left" || root.position === "right" ? root.barSize : backdrop.width
                        height: root.position === "top" || root.position === "bottom" ? root.barSize : backdrop.height
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.AllButtons
                    onPressed: root.dismiss()
                }
            }
        }
    }
}
