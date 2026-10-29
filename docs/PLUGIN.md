# Plugin architecture and host contract

Status: proposed implementation for the inspected Quickshell-based Omarchy.
Select and record an actual supported host/version range before release.

## Proposed layout

```text
manifest.json             added only with working, validated entrypoints
BarWidget.qml             bar indicator and click/keyboard interaction
Panel.qml                 explicit host-summoned compact panel
components/               controls/rendering without hardware semantics
client/                   bounded socket adapter and view model
tests/                    contract fixtures, QML and host scenarios
docs/
```

The planned manifest declares `bar-widget` and `panel` kinds, with matching
`entryPoints.barWidget` and `entryPoints.panel`. Avoid loading multiple socket
clients merely because both entrypoints exist: share a plugin-owned connection
where supported by the host, or use bounded independent clients with one
clearly owned lifecycle. No private first-party service access is assumed.

Installed files belong under `~/.config/omarchy/plugins/srdiogo.minifuse/`.
Do not patch packaged `/usr/share/omarchy` files, replace the built-in bar or
edit the existing audio plugin to add device-specific control logic.

## Data/control flow

Connect with Quickshell's local socket facilities to the service, negotiate
API/capabilities and fetch a baseline before enabling controls. Receive bounded
state events and reconnect after service restart/gaps. Never synchronously
launch `mf-cli` for every slider movement or parse human-readable terminal text.

Use domain plans/apply and operation identity from the canonical service
contract, including the negotiated `live_controls` feature. Read state on
connection and follow subscriptions; manual refresh belongs in diagnostics. The
master slider renders locally, sends coalesced intermediate samples and
preserves its final value on release. Use one in-flight sample plus one latest
desired value, with the service retaining per-sample evidence.
Show verified state only after settlement; a timeout requires outcome query,
not a new write. The shell event loop never performs blocking hardware work.

Omarchy plugins run in the shared shell process. Keep the adapter small, bound
all frame/subscriber memory and handle malformed/incompatible server data.
Plugin unload/hot reload closes its own subscriptions and never cancels or
replays a transaction already admitted by the service.

## Panel contents

- Device/connection state and a concise unavailable/error explanation.
- Selected mix and its confirmed route; make bypassed-master behavior clear.
- Master configured level with numeric value, continuous adjustment feedback and
  supported mute affordances. Do not invent a hardware master-mute selector;
  any UI mute must use an explicitly designed core operation/capability.
- Preset inspection/restore planning with an explicit apply step, or opening
  the full application when the compact panel cannot show a sufficient preview.
- Open Full Application as a deliberate action, with missing-app feedback.

Show switch indicators only when reliable readback is advertised. Keep host
PipeWire volume, configured mix levels and measured signal meters distinct.
Apply the host's theme, scaling and accessibility conventions without changing
device state on theme updates or component construction.

## Activation and desktop agent

Bar clicks and keyboard actions can open the panel directly. For the physical
button, the desktop agent chooses the configured target and invokes the
plugin's explicit summon entrypoint. Keep the plugin ID stable across releases.
The plugin does not independently respond to `control_panel_requested` by
opening another window or launching the application.

If the plugin is disabled/not installed, the agent reports the missing target
according to user preference. Installing the plugin is not sufficient to
observe a button while the service/agent are stopped. Agent and service startup
remain explicit optional session configuration.

## References

- [Omarchy shell/plugin contract](https://github.com/basecamp/omarchy/blob/quattro/shell/README.md)
- [Quickshell overview](https://quickshell.org/about/)
- [Quickshell local socket](https://quickshell.org/docs/v0.3.1/types/Quickshell.Io/Socket/)

These sources informed the design; dependency versions are not pinned by a URL
to a moving documentation branch. Record a tested host release/commit in the
first implementation's compatibility table.

## Service contract baseline

`contract.lock.json` pins the implemented service revision and canonical fixture
SHA-256, including continuous-control admission/intermediate/final results. This
is an implementation prerequisite; it does not advertise a functioning plugin
or claim a tested host compatibility range.
