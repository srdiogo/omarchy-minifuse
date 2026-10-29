#!/usr/bin/env python3
"""Validate distribution entrypoints and the pinned canonical service fixture."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, default=Path("/usr/share/omarchy/shell"))
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert manifest["schemaVersion"] == 1 and manifest["id"] == "srdiogo.minifuse"
    assert set(manifest["kinds"]) == {"service", "bar-widget", "panel"}
    for path in manifest["entryPoints"].values():
        assert not Path(path).is_absolute() and ".." not in Path(path).parts
        assert (ROOT / path).is_file()
    lock = json.loads((ROOT / "contract.lock.json").read_text())
    fixture = ROOT / lock["fixture"]
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == lock["sha256"]
    assert lock["api_major"] == 1
    subprocess.run(
        ["python3", "-I", str(ROOT / "client/bridge.py"), "--help"],
        check=True,
        capture_output=True,
    )
    with tempfile.TemporaryDirectory(prefix="minifuse-qml-imports-") as folder:
        host = args.host
        if host.exists():
            (Path(folder) / "qs").symlink_to(host, target_is_directory=True)
            subprocess.run(
                [
                    "/usr/lib/qt6/bin/qmllint",
                    "-I",
                    folder,
                    "--missing-property",
                    "disable",
                    "--signal-handler-parameters",
                    "disable",
                    *[str(ROOT / name) for name in manifest["entryPoints"].values()],
                    *[str(path) for path in (ROOT / "components").glob("*.qml")],
                ],
                check=True,
            )
    print(
        "Manifest, entrypoint files, fixture pin, bridge help and available QML tooling passed."
    )


if __name__ == "__main__":
    main()
