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
failure before admission, exclusive ownership and private archival files. Launcher checks cover fixed
arguments, missing-app feedback and survival independently of the client lifetime.

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

## Installed Wayland shell acceptance

The plugin was installed in the user-owned plugin directory and enabled through
the host command. Three summon/hide cycles each produced exactly one native
layer surface and one helper, with no tiled application window. The tested
surface was 385 × 427 logical units at the current theme/font scale.

Disable removed the helper. Re-enable and a full plugin rescan converged on one
helper again. The installed GUI launcher was exercised through the same bridge
command used by the panel; one standalone GUI instance remained alive after the
bridge and plugin were stopped. The complete decoded device state and unrelated
shell configuration captured at the start of this acceptance test were unchanged.

This host retained a previously compiled component during a structural UI type
change. A supported `omarchy restart shell` loaded the new implementation; this
is distinct from an ordinary source/metadata rescan. No packaged host files or
compositor rules were modified. The initial shell configuration was backed up.

Broader device/kernel/rate/scaling coverage remains open; this report does not
promote fixture coverage into hardware acceptance.


## Mixer panel layout revision

The redesigned panel uses original components, inspired by Omarchy360's strip
bank and the MiniFuse 4 manual's channel/master organization. Fixture checks
cover normal, direct-route, disconnected and uncertain states at 1080, 600 and
480 logical pixels. Status/theme/meter updates are allowed to settle across
frames before checking fixed footer positions and stable source delegates.
Construction, readback, focus and theme changes must emit zero control commands.

The client suite additionally verifies source-level coalescing and final release,
fixed gesture targets, pan/silence/range gates, typed solo plans, optional meter
subscription, stale expiry, device identity and malformed samples. Existing
operation recovery and no-replay tests remain in place. These are deterministic
fixture tests; the new source control paths have not been revalidated against
physical hardware. The previously recorded hardware evidence applies only to
the controls and versions explicitly listed above.
