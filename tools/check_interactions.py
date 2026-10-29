#!/usr/bin/env python3
"""Send pointer events only to an isolated fixture window with a fake backend."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from check_host import ROOT, fixture_view


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, default=Path("/usr/share/omarchy/shell"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="minifuse-interaction-check-") as name:
        folder = Path(name)
        for module in ["Commons", "Ui"]:
            (folder / module).symlink_to(args.host / module, target_is_directory=True)
        (folder / "Plugin").symlink_to(ROOT, target_is_directory=True)
        (folder / "runtime").mkdir(mode=0o700)
        source = (
            (ROOT / "tests/qml/InteractionHarness.qml")
            .read_text()
            .replace("VIEW", json.dumps(fixture_view()))
        )
        (folder / "shell.qml").write_text(source)
        env = {
            **os.environ,
            "QT_QUICK_BACKEND": "software",
            "QT_QPA_PLATFORM": "offscreen",
            "QT_QPA_PLATFORMTHEME": "",
            "QT_QUICK_CONTROLS_STYLE": "Basic",
            "XDG_RUNTIME_DIR": str(folder / "runtime"),
        }
        result = subprocess.run(
            ["quickshell", "--path", str(folder), "--no-color"],
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )
        output = result.stdout + result.stderr
        if (
            result.returncode
            or "INTERACTION_CHECK_PASSED" not in output
            or any(
                token in output
                for token in [
                    "ReferenceError",
                    "TypeError",
                    "Unable to assign",
                    "Binding loop",
                    "binding loop",
                ]
            )
        ):
            print(output)
            raise SystemExit("Pointer interaction check failed")
        print(output)
        print(
            "Focused mute/solo state, first-press source/pan/master gestures and bar toggling passed without real device access."
        )


if __name__ == "__main__":
    main()
