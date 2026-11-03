#!/usr/bin/env python3
"""Run isolated host rendering and pointer tests; no device access."""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "normal": 1080,
    "direct": 600,
    "uncertain": 480,
    "offline": 840,
    "meters": 840,
    "mf1": 840,
    "mf2": 840,
    "mf2_otg": 840,
    "initialization": 840,
    "mf1_loopback": 840,
    "mf2_loopback": 840,
    "mf2_otg_loopback": 840,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, default=Path("/usr/share/omarchy/shell"))
    parser.add_argument(
        "--qmllint", type=Path, default=Path("/usr/lib/qt6/bin/qmllint")
    )
    args = parser.parse_args()
    common = ["--host", str(args.host.resolve())]
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/check_project.py"),
            *common,
            "--qmllint",
            str(args.qmllint.resolve()),
        ],
        check=True,
    )
    for scenario, width in SCENARIOS.items():
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/check_host.py"),
                *common,
                "--scenario",
                scenario,
                "--width",
                str(width),
            ],
            check=True,
        )
    for scenario in ("normal", "mf1_loopback", "mf2_loopback", "mf2_otg_loopback"):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/check_interactions.py"),
                *common,
                "--scenario",
                scenario,
            ],
            check=True,
        )
    print(
        "Twelve host layouts and four pointer-interaction scenarios passed without hardware access."
    )


if __name__ == "__main__":
    main()
