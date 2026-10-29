#!/usr/bin/env python3
"""Construct entrypoints in an isolated shell with the installed host modules."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, default=Path("/usr/share/omarchy/shell"))
    parser.add_argument(
        "--visible", action="store_true", help="Show the independent test window"
    )
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--width", type=int)
    parser.add_argument(
        "--scenario",
        choices=["normal", "direct", "offline", "uncertain", "meters"],
        default="normal",
    )
    args = parser.parse_args()
    fixture = json.loads((ROOT / "tests/contract/v1.json").read_text())
    state = fixture["input_state"]["result"]
    import importlib.util

    spec = importlib.util.spec_from_file_location("bridge", ROOT / "client/bridge.py")
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    reduced, _ = bridge.state_view(state)
    view = dict(
        status="Confirmed device state",
        connected=True,
        can_write=True,
        busy=False,
        live=False,
        uncertain=False,
        can_acknowledge=False,
        message="Device readback verified",
        live_target=None,
        meters=None,
        selected="out12",
        mixes=reduced,
        inputs=state["state"]["inputs"],
    )
    if args.scenario == "meters":
        view["meters"] = {
            "sources": [-24, -35, None, None, -15, -15, -30, -30, None, None],
            "mixes": [[-20, -20], [None, None], [None, None]],
        }
    elif args.scenario == "direct":
        view["mixes"][0]["route"] = "usb12"
    elif args.scenario == "offline":
        view.update(
            connected=False,
            can_write=False,
            mixes=[],
            inputs={},
            status="Service unavailable",
        )
    elif args.scenario == "uncertain":
        view.update(
            uncertain=True,
            can_write=False,
            can_acknowledge=True,
            message="Outcome uncertain. Inspect current state before acknowledging; no write will be replayed.",
        )
    with tempfile.TemporaryDirectory(prefix="minifuse-host-check-") as folder:
        folder = Path(folder)
        for name in ["Commons", "Ui", "services"]:
            (folder / name).symlink_to(args.host / name, target_is_directory=True)
        (folder / "Plugin").symlink_to(ROOT, target_is_directory=True)
        (folder / "plugins").mkdir()
        (folder / "runtime").mkdir(mode=0o700)
        capture = str(args.capture.resolve()) if args.capture else ""
        source = (
            """
import QtQuick
import Quickshell
import qs.Commons
import "services" as Services
import "Plugin" as Plugin
import "Plugin/components" as Components
ShellRoot {
    id: root
    property int dispatches: 0
    property int attempts: 0
    property int phase: 0
    property var before: null
    property var originalModel: null
    property var model: VIEW
    QtObject {
        id: backend
        property var model: root.model
        function command(value) { root.dispatches += 1 }
    }
    Services.PluginRegistry {
        id: registry
        pluginsDir: PLUGINS
    }
    QtObject {
        id: facade
        function serviceFor(id) { return id === "srdiogo.minifuse" ? backend : null }
        function summon(id, payload) { return true }
        function hide(id) { return true }
    }
    QtObject {
        id: bar
        property var shell: facade
        property bool vertical: false
        property int barSize: 32
    }
    Plugin.Service { id: realEntry }
    Plugin.BarWidget { id: widget; bar: bar }
    FloatingWindow {
        visible: true
        implicitWidth: WIDTH > 0 ? WIDTH : panel.implicitWidth
        implicitHeight: panel.implicitHeight
        color: Color.popups.background
        Components.QuickControls { id: panel; width: parent.width; height: implicitHeight; backend: backend }
    }
    Component.onCompleted: {
        if (!registry.validateManifest(MANIFEST, "test")) throw new Error("Manifest rejected by host")
        panel.focusInitial()
    }
    Timer {
        interval: 100
        repeat: true
        running: true
        onTriggered: {
            if (realEntry.model.status !== "Service unavailable") {
                root.attempts += 1
                if (root.attempts >= 50) throw new Error("Helper startup deadline expired")
                return
            }
            if (root.phase === 0) {
                if ((root.model.connected && !panel.selected) || !widget.backend) throw new Error("Entrypoint integration failed")
                if (realEntry.model.connected) throw new Error("Real service entrypoint lifecycle failed")
                root.before = panel.layoutSnapshot()
                root.originalModel = root.model
                Color.accent = "#88c0d0"
                Color.background = "#20242c"
                root.model = Object.assign({}, root.model, {message: "Device readback verified ".repeat(20), busy: true, meters: {sources: [-25,-30,null,null,-18,-18,null,null,null,null], mixes: [[-20,-20],[null,null],[null,null]]}})
                panel.focusInitial()
                root.phase = 1
                return
            }
            if (root.phase === 1) {
                const after = panel.layoutSnapshot()
                if (root.before.footerY !== after.footerY) throw new Error("Status feedback moved the controls")
                if (root.before.strips[0] && root.before.strips[0] !== after.strips[0]) throw new Error("Readback recreated source delegates")
                root.model = root.originalModel
                root.phase = 2
                return
            }
            if (root.phase === 2) {
                root.model = Object.assign({}, root.model, {connected: false, can_write: false, mixes: [], inputs: {}, meters: null, busy: false})
                root.phase = 3
                return
            }
            if (root.phase === 3) {
                if (panel.selected || panel.layoutSnapshot().sourceCount !== 0) throw new Error("Disconnected mixer retained source views")
                root.model = root.originalModel
                root.phase = 4
                return
            }
            stop()
            const after = panel.layoutSnapshot()
            if (root.dispatches !== 0) throw new Error("Construction/theme/readback/focus dispatched a command")
            if (after.masterX + 100 > panel.width || after.sourceAreaWidth <= 0) throw new Error("Master or source viewport clipped")
            if (after.sourceContentHeight > after.masterHeight + 1) throw new Error("Source/master heights differ")
            console.log("HOST_CHECK_PASSED", JSON.stringify({width: after.width, height: after.height, footerY: after.footerY, sources: after.sourceCount}))
            if (CAPTURE !== "") {
                panel.grabToImage(function(result) {
                    result.saveToFile(CAPTURE)
                    Qt.quit()
                })
                return
            }
            Qt.quit()
        }
    }
}
""".replace("VIEW", json.dumps(view))
            .replace("WIDTH", str(args.width or 0))
            .replace("PLUGINS", json.dumps(str(folder / "plugins")))
            .replace("MANIFEST", (ROOT / "manifest.json").read_text())
            .replace("CAPTURE", json.dumps(capture))
        )
        (folder / "shell.qml").write_text(source)
        env = dict(
            os.environ,
            QT_QUICK_BACKEND="software",
            XDG_RUNTIME_DIR=str(folder / "runtime"),
            XDG_STATE_HOME=str(folder / "state"),
        )
        if not args.visible:
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["QT_QPA_PLATFORMTHEME"] = ""
            env["QT_QUICK_CONTROLS_STYLE"] = "Basic"
        try:
            result = subprocess.run(
                ["quickshell", "--path", str(folder), "--no-color"],
                env=env,
                text=True,
                capture_output=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired as error:
            print((error.stdout or b"").decode(errors="replace"))
            print((error.stderr or b"").decode(errors="replace"))
            raise SystemExit("Host construction timed out")
        output = result.stdout + result.stderr
        if (
            result.returncode
            or "HOST_CHECK_PASSED" not in output
            or any(
                token in output
                for token in (
                    "ReferenceError",
                    "TypeError",
                    "Error:",
                    "Unable to assign",
                    "binding loop",
                    "Binding loop",
                )
            )
        ):
            print(output)
            raise SystemExit("Host construction check failed")
        print(output)
        print(
            "Isolated host service/bar/content construction, manifest and zero-write checks passed."
        )


if __name__ == "__main__":
    main()
