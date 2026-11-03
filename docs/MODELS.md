# Model-specific native controls

The panel consumes the backend's versioned model profile and confirmed state.
It never sends USB commands, applies firmware changes or substitutes an MF4
layout for another model. Basic input indicators remain read-only; open the full
application for INST, +48 V, direct-monitor changes and preset management.

The native `loopback_mixer` profile requires an explicit backend opt-in, matching
module capabilities and compatible firmware: MF1/MF2 1.5.x or OTG 1.0.x. The panel
requires matching confirmed-state/inventory firmware metadata before allowing
writes. Missing or unreviewed versions stay disabled. Hardware acceptance is
pending separately for every new model.

| Model | Native sources | Meter readings |
|---|---|---|
| MF1 | Analog 1, USB 1–2, USB 3–4 | Input 1, loopback L/R |
| MF2 | Analog 1, Analog 2, USB 1–2, USB 3–4 | Inputs 1/2, loopback L/R |
| MF2 OTG | Analog 1, Analog 2, USB 1–2, USB 5–6 | Inputs 1/2, loopback L/R, OTG L/R |

One native loopback bus provides source gain/mute, analog pan and stereo master.
USB playback pairs link gain/mute; they have no pan, solo or individual native
peak readings. Independent buttons control loopback enable, duplicate recording
on USB 1–2 and monitoring on physical outputs/phones. OTG adds Main → OTG,
OTG → monitoring and front-panel LED meter-source selectors. No unverified
OTG-source gain fader is synthesized. Input/output gain knobs remain physical.

Native meters use their own bounded input/loopback/OTG arrays and expire after
500 ms. They do not reuse MF4's source/mix arrays or assert physical output
calibration. Windows SLS virtual-device mixes are separate host processing and
are not provided. Presets remain in the full application and preserve input
modes, +48 V, direct monitoring and opaque device fields on restore.

Faders keep stable delegates while the service verifies changes. Mutations use
the existing typed, journaled plan or live-control methods, with no replay after
an uncertain operation. Constructing, focusing, refreshing or recoloring the
panel sends no mutations. Initialization mode has no audio controls.

`tests/contract/loopback-v1.json` is generated synthetic backend data, not a
capture. Host checks render all three native layouts and exercise their pointer controls
on both pinned Omarchy/Quickshell/Qt generations, including Qt 6.12. A successful software test does not establish
physical compatibility or support for an untested host version. Follow the
[backend acceptance guide](https://github.com/srdiogo/minifuse-backend/blob/feature/model-controls/docs/models/TESTING.md)
for firmware checks, read-only capture, controlled audio tests and reporting.

The model fixtures are pinned to the backend source revision and file hashes in
[model-contract.lock.json](../model-contract.lock.json).
