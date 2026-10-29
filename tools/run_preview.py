#!/usr/bin/env python3
"""Run the real plugin panel independently of the user's Omarchy bar."""

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
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="minifuse-panel-preview-") as folder:
        folder = Path(folder)
        for name in ["Commons", "Ui"]:
            (folder / name).symlink_to(args.host / name, target_is_directory=True)
        (folder / "Plugin").symlink_to(ROOT, target_is_directory=True)
        source = """
import QtQuick
import Quickshell
import Quickshell.Io
import "Plugin" as Plugin
ShellRoot {
    id: root
    property bool shown: false
    Plugin.Service { id: backend }
    QtObject {
        id: facade
        function serviceFor(id) { return id === "srdiogo.minifuse" ? backend : null }
        function hide(id) { panel.close(); return true }
    }
    Plugin.Panel {
        id: panel
        shell: facade
        service: backend
        onOpenedChanged: if (!opened && root.shown) Qt.quit()
    }
    IpcHandler {
        target: "minifuse-preview"
        function status(): string { return JSON.stringify(backend.model) }
        function close(): void { panel.dismiss() }
    }
    Component.onCompleted: {
        panel.open("{}")
        shown = true
    }
}
"""
        (folder / "shell.qml").write_text(source)
        state = (
            Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
            / "minifuse-plugin-preview"
        )
        env = {**os.environ, "XDG_STATE_HOME": str(state)}
        print(
            json.dumps({"configuration": str(folder), "client_state_base": str(state)}),
            flush=True,
        )
        subprocess.run(
            ["quickshell", "--path", str(folder), "--no-color"], env=env, check=True
        )


if __name__ == "__main__":
    main()
