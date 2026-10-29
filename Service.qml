import QtQuick
import Quickshell.Io

Item {
    id: root
    property var shell: null
    property var manifest: null
    property var model: ({status: "Starting MiniFuse client", message: "", connected: false,
        can_write: false, busy: false, live: false, uncertain: false,
        can_acknowledge: false, selected: "out12", mixes: [], inputs: {}})

    function command(value) {
        if (helper.running)
            helper.write(JSON.stringify(value) + "\n")
    }

    Process {
        id: helper
        command: ["python3", "-I", decodeURIComponent(Qt.resolvedUrl("client/bridge.py").toString().replace(/^file:\/\//, ""))]
        stdinEnabled: true
        stdout: SplitParser {
            onRead: function(data) {
                if (data.length > 32768) {
                    helper.running = false
                    return
                }
                try {
                    const value = JSON.parse(data)
                    if (value && typeof value.connected === "boolean" && Array.isArray(value.mixes))
                        root.model = value
                } catch (error) {
                    helper.running = false
                }
            }
        }
        onExited: function() {
            root.model = {status: "MiniFuse client stopped", message: "Check Python 3.12+ and the private client state directory",
                connected: false, can_write: false, busy: false, live: false,
                uncertain: false, can_acknowledge: false, selected: "out12", mixes: [], inputs: {}}
            retry.start()
        }
    }
    Timer {
        id: retry
        interval: 2000
        onTriggered: helper.running = true
    }
    Component.onCompleted: helper.running = true
    Component.onDestruction: helper.running = false
}
