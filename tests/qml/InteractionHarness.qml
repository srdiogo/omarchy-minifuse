import QtQuick
import QtTest as Test
import Quickshell
import "Plugin" as Plugin
import "Plugin/components" as Components

ShellRoot {
    id: root
    property var model: VIEW
    property var commands: []
    property int phase: 0
    property int dismissals: 0
    property int toggles: 0
    property bool panelOpen: false
    property var level: null
    property var pan: null
    property var master: null
    property real initialLevel: 0

    function require(condition, message) { if (!condition) throw new Error(message) }
    function find(item, name) {
        if (item.objectName === name) return item
        for (const child of item.children || []) {
            const found = find(child, name)
            if (found) return found
        }
        return null
    }
    function verifyFinal(action) {
        require(commands.length > 0 && commands.every(c => c.action === action), "Unexpected gesture action")
        require(commands[commands.length - 1].finish === true, "Release did not flush the final value")
        require(commands.filter(c => c.finish).length === 1, "Gesture ended more than once")
    }
    QtObject {
        id: backend
        property var model: root.model
        function command(command) {
            root.commands = root.commands.concat([command])
            if (command.action === "open_app") return
            const next = JSON.parse(JSON.stringify(root.model))
            const mix = next.mixes.find(m => m.mix === next.selected)
            const channel = mix.channels.find(c => c.source === command.source)
            if (command.action === "mute" || command.action === "solo") channel[command.action] = command.value
            else {
                if (command.action === "master") mix.master_db = command.value
                else channel[command.action === "level" ? "level_db" : "pan"] = command.value
                next.busy = !command.finish
                next.live = !command.finish
                next.live_target = command.finish ? null : {kind: ({level: "channel_level", pan: "channel_pan", master: "master_level"})[command.action], source: command.source, mix: mix.mix}
            }
            root.model = next
        }
    }
    QtObject {
        id: facade
        function serviceFor(id) { return backend }
        function toggle(id, payload) { root.panelOpen = !root.panelOpen; root.toggles += 1; return true }
    }
    QtObject {
        id: bar
        property var shell: facade
        property bool vertical: false
        property int barSize: 32
        property string position: "top"
    }
    Plugin.BarWidget { id: widget; bar: bar }
    Test.TestEvent { id: events }
    FloatingWindow {
        visible: true
        implicitWidth: 1080
        implicitHeight: panel.implicitHeight
        Components.QuickControls {
            id: panel; width: parent.width; height: implicitHeight; backend: backend
            onDismissRequested: root.dismissals += 1
        }
    }
    Timer {
        interval: 60
        running: true
        repeat: true
        onTriggered: {
            try {
                if (root.phase === 0) {
                    root.require(root.commands.length === 0, "Readback produced commands")
                    const mute = root.find(panel, "mute-analog1")
                    const solo = root.find(panel, "solo-analog1")
                    root.require(!!mute && !!solo, "Switch controls not found")
                    const initialMute = mute.active
                    events.mouseClick(mute, mute.width / 2, mute.height / 2, Qt.LeftButton, Qt.NoModifier, 0)
                    root.require(mute.active !== initialMute && mute.activeFocus, "Mute state is unclear while focused")
                    const firstColor = mute.contentItem.color.toString()
                    events.mouseClick(mute, mute.width / 2, mute.height / 2, Qt.LeftButton, Qt.NoModifier, 0)
                    root.require(mute.active === initialMute && mute.contentItem.color.toString() !== firstColor, "Mute focus hid its confirmed state")
                    const initialSolo = solo.active
                    events.mouseClick(solo, solo.width / 2, solo.height / 2, Qt.LeftButton, Qt.NoModifier, 0)
                    root.require(solo.active !== initialSolo && solo.activeFocus, "Solo state is unclear while focused")
                    events.mouseClick(solo, solo.width / 2, solo.height / 2, Qt.LeftButton, Qt.NoModifier, 0)
                    root.require(solo.active === initialSolo, "Solo did not return to its original state")
                    events.keyClick(Qt.Key_Space, Qt.NoModifier, 0)
                    root.require(solo.active !== initialSolo && solo.activeFocus, "Keyboard toggle lost its state or focus")
                    events.keyClick(Qt.Key_Space, Qt.NoModifier, 0)
                    root.require(solo.active === initialSolo, "Keyboard toggle did not restore the initial state")
                    widget.open(); widget.open()
                    root.require(root.toggles === 2 && !root.panelOpen, "Bar button did not toggle the panel")
                    root.commands = []
                    root.level = root.find(panel, "level-analog1")
                    root.require(!!root.level && root.level.enabled, "Source fader unavailable")
                    events.mousePress(root.level, root.level.width / 2, root.level.height * 0.65, Qt.LeftButton, Qt.NoModifier, 0)
                } else if (root.phase === 1) {
                    root.require(root.commands.length > 0 && root.commands.every(c => !c.finish) && root.level.pressed, "First press ended the source gesture")
                    root.initialLevel = root.level.value
                    events.mouseMove(root.level, root.level.width / 2, root.level.height * 0.35, 0, Qt.LeftButton, Qt.NoModifier)
                } else if (root.phase === 2) {
                    root.require(root.level.value !== root.initialLevel && root.commands.every(c => !c.finish), "First drag did not update continuously")
                    events.mouseRelease(root.level, root.level.width / 2, root.level.height * 0.35, Qt.LeftButton, Qt.NoModifier, 0)
                } else if (root.phase === 3) {
                    root.verifyFinal("level")
                    root.commands = []
                    root.pan = root.find(panel, "pan-analog1")
                    root.require(!!root.pan && root.pan.enabled, "Pan slider unavailable")
                    events.mousePress(root.pan, root.pan.width * 0.2, root.pan.height / 2, Qt.LeftButton, Qt.NoModifier, 0)
                } else if (root.phase === 4) {
                    root.require(root.commands.length > 0 && root.commands.every(c => !c.finish) && root.pan.pressed, "First press ended the pan gesture")
                    events.mouseMove(root.pan, root.pan.width * 0.8, root.pan.height / 2, 0, Qt.LeftButton, Qt.NoModifier)
                } else if (root.phase === 5) {
                    events.mouseRelease(root.pan, root.pan.width * 0.8, root.pan.height / 2, Qt.LeftButton, Qt.NoModifier, 0)
                } else if (root.phase === 6) {
                    root.verifyFinal("pan")
                    root.commands = []
                    root.master = root.find(panel, "master-fader")
                    events.mousePress(root.master, root.master.width / 2, root.master.height * 0.6, Qt.LeftButton, Qt.NoModifier, 0)
                } else if (root.phase === 7) {
                    root.require(root.commands.length > 0 && root.commands.every(c => !c.finish), "First press ended the master gesture")
                    events.mouseMove(root.master, root.master.width / 2, root.master.height * 0.3, 0, Qt.LeftButton, Qt.NoModifier)
                } else if (root.phase === 8) {
                    events.mouseRelease(root.master, root.master.width / 2, root.master.height * 0.3, Qt.LeftButton, Qt.NoModifier, 0)
                } else {
                    root.verifyFinal("master")
                    root.commands = []
                    const launcher = root.find(panel, "open-full-mixer")
                    events.mouseClick(launcher, launcher.width / 2, launcher.height / 2, Qt.LeftButton, Qt.NoModifier, 0)
                    root.require(root.commands.length === 1 && root.commands[0].action === "open_app" && root.dismissals === 1, "Full-app handoff did not dismiss the panel")
                    console.log("INTERACTION_CHECK_PASSED")
                    Qt.quit()
                }
                root.phase += 1
            } catch (error) {
                console.error("INTERACTION_CHECK_FAILED", error)
                Qt.exit(1)
            }
        }
    }
}
