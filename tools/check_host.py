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
    args = parser.parse_args()
    fixture = json.loads((ROOT / "tests/contract/v1.json").read_text())
    state = fixture["input_state"]["result"]
    reduced = [
        dict(
            mix=m["mix"],
            master_db=m["master_db"],
            route=m["route"],
            routes=next(
                c["routes"]
                for c in state["capabilities"]["mixes"]
                if c["mix"] == m["mix"]
            ),
            channels=[dict(source=c["channel"], mute=c["mute"]) for c in m["channels"]],
        )
        for m in state["state"]["mixes"]
    ]
    view = dict(
        status="Confirmed device state",
        connected=True,
        can_write=True,
        busy=False,
        live=False,
        uncertain=False,
        can_acknowledge=False,
        message="Device readback verified",
        selected="out12",
        mixes=reduced,
        inputs=state["state"]["inputs"],
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
ShellRoot {
    id: root
    property int dispatches: 0
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
        function summon(id, payload) { panel.open(payload); return true }
        function hide(id) { panel.close(); return true }
    }
    QtObject {
        id: bar
        property var shell: facade
        property bool vertical: false
        property int barSize: 32
    }
    Plugin.Service { id: realEntry }
    Plugin.BarWidget { id: widget; bar: bar }
    Plugin.Panel { id: panel; shell: facade; service: backend }
    Component.onCompleted: {
        if (!registry.validateManifest(MANIFEST, "test")) throw new Error("Manifest rejected by host")
        panel.open("{}")
    }
    Timer {
        interval: 500
        running: true
        onTriggered: {
            if (!panel.opened || !panel.selected || !widget.backend) throw new Error("Entrypoint integration failed")
            if (realEntry.model.connected || realEntry.model.status !== "Service unavailable") throw new Error("Real service entrypoint lifecycle failed")
            const initial = root.dispatches
            Color.accent = "#88c0d0"
            Color.background = "#20242c"
            root.model = Object.assign({}, root.model, {message: "", busy: false})
            if (root.dispatches !== initial || initial !== 0) throw new Error("Construction/theme/readback dispatched a command")
            panel.close()
            panel.open("{}")
            if (root.dispatches !== 0) throw new Error("Summon lifecycle dispatched a command")
            console.log("HOST_CHECK_PASSED")
            if (CAPTURE !== "") {
                const objects = panel.resources
                for (let i=0; i<objects.length; ++i) {
                    if (objects[i].contentItem) {
                        objects[i].contentItem.children[0].grabToImage(function(result) {
                            result.saveToFile(CAPTURE)
                            Qt.quit()
                        })
                        return
                    }
                }
                throw new Error("Capture surface unavailable")
            }
            Qt.quit()
        }
    }
}
""".replace("VIEW", json.dumps(view))
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
            "Isolated host construction, manifest, summon and zero-write checks passed."
        )


if __name__ == "__main__":
    main()
