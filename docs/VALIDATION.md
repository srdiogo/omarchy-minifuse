# Validation evidence and limits

## Automated client checks

The standard-library test suite uses the pinned canonical service fixtures and
private Unix sockets. It covers strict UTF-8/JSON (including duplicate keys and
nonfinite values), frame size/deadline bounds, fragmented baseline delivery,
zero mutations on connection, coalesced controls with a preserved final sample,
capability-gated routes/source mute, direct-route master bypass, unsupported
models, external state interruption and sequence-gap invalidation.

Recovery checks cover uncertain apply acknowledgement, query without replay,
explicit unknown-outcome acknowledgement, refusal to acknowledge pending work,
retention of an admitted gesture after a later rejected sample, identity-store
failure before admission, exclusive ownership and private archival files.

`tools/check_project.py` validates manifest paths, fixture SHA-256 and bridge
help. QML lint suppresses host metadata categories for QObject-backed dynamic
style/facade members, the absent C++ QProcess exit-status enum and runtime-selected
PanelWindow backend types. Real component and Wayland surface checks exercise
these paths; other lint diagnostics remain enabled.

## Host components

`tools/check_host.py` constructs the actual service entrypoint, bar widget and
shared QuickControls content inside an independent offscreen configuration,
using the installed or pinned host's Commons/Ui and PluginRegistry. It validates
the manifest with the host, follows a readback change and changes theme tokens
while asserting zero command dispatches. The real helper entrypoint also starts
and reports the deliberately unavailable test service. A rendered panel was
inspected for layout and contrast. Offscreen Qt has no layer-shell backend, so
native panel mapping/summon/focus behavior is checked in the real Wayland session.

The pinned Omarchy 4.0.4 source matches the installed 4.0.4-1 host's registry,
scoped facade, shell loader, Button, Dropdown and Style files. Runtime baseline:
Quickshell 0.3.1, Qt 6.11.2, Python 3.14.7. CI also checks the client on Python
3.12 and 3.14 and constructs the pinned host components using the 2026-09-13
Arch repository snapshot, which provides the tested Quickshell/Qt packages.
The current rolling repository already provides newer runtimes; it is not
substituted for this compatibility baseline.

## MiniFuse 4 smoke validation

The real helper connected to the existing service and read all three mix views
and the reliable input indicators. Changing the selected view among out12,
out34 and loopback left the complete decoded device state unchanged. Closing
its stdin stopped the client successfully.

A bounded master test used out34, with speakers on outputs 1–2. The confirmed
master moved from 0 dB to -0.5 dB and back to 0 dB through the plugin's continuous
operation path. Both results were verified and archived. The complete decoded
state after restoration exactly matched the initial state, including inputs,
channel configuration, routes and opaque fields.

Real `plan_changes` requests for an out34 USB34 route and source mute were
accepted with predicted states; they were not applied. Thus this smoke test
validates real domain planning, not additional audible route/mute acceptance.
No audio signal was injected. Firmware, effects, device-storage writes and
input-switch writes were not part of this plugin test.

Installed-shell enable/disable, reload subscription ownership and the optional
application handoff are tracked separately from isolated component construction.
Broader device/kernel/rate/scaling coverage remains open; this report does not
promote fixture coverage into hardware acceptance.
