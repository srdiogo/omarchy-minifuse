# Client architecture and host contract

The root manifest exposes `service`, `bar-widget` and `panel` entrypoints under
`srdiogo.minifuse`. The service entry owns one `Quickshell.Io.Process`; the bar
and panel look up only that plugin's service through the host-scoped facade.
Multiple bar surfaces never create additional device subscriptions. A replacement
bar that withholds the service facade displays an unavailable indicator.

## Connection ownership

`client/bridge.py` is an isolated standard-library Python client. Its process
uses the canonical newline-delimited JSON API directly; it does not run or parse
`mf-cli`. A helper rather than a raw QML `SplitParser` on the service socket
allows byte-level UTF-8/duplicate-key validation, partial-frame deadlines,
peer-UID checks and durable operation references without blocking the shared
shell event loop. This is a transport/presentation adapter, not another device
service. All hardware semantics, USB access, rollback and verification stay in
mf-service/mf-core.

One connection negotiates API 1 and the required plans, subscriptions, durable
operations and continuous-control features. Its atomic subscription baseline
contains inventory, capabilities, confirmed states and sequence. No delta applies
before that baseline. Inventory changes, sequence gaps, epoch changes, invalid
frames and service loss close the connection and clear writable state. Reconnect
obtains a fresh baseline and queries retained operation identities. It does not
replay a gesture, route change, mute or preset.

Limits are 256 KiB per service frame including LF, a two-second partial-frame
deadline, eight outstanding requests, 16 inventory/mix entries, 32 sources per
mix, 4 KiB panel commands and 32 KiB projected view frames. The asyncio reader
has bounded flow-control buffering. A single output worker plus a one-slot,
replaceable view queue bounds retained presentation data when the shell is slow.
Readback and theme changes never create mutations. Reconnect backs off two seconds.

The helper is launched as a fixed argument vector with Python isolated mode and
a path resolved inside this plugin. Panel commands have a closed action set.
The only application launch is the fixed `minifuse-control` executable. There is
no shell command interpolation, root request, module loading or raw USB path.

## Operations and recovery

The confirmed state supplies device/generation/revision tokens and the advertised
mix/route/source inventory. The client never derives identity from USB addresses
or UI positions. Source mute and route actions use domain plan/apply. Plan expiry
or conflict is visible; a failed plan is not rebuilt and applied automatically.

Master gestures use `begin_control` and contiguous `update_control` sequences.
There is at most one unsettled sample and one replaceable desired value. Samples
are separated by at least 80 ms; release remains a final sample. Acknowledgement
is admission, not verification. Own confirmed-state events preserve the preview;
unassociated revision changes stop the old gesture. An interrupted control
retains confirmed changes without replaying the final pointer position.

A private client token and locally generated idempotency key are saved and
fsynced before admission. Terminal records are archived before the pending
reference is cleared. A rejected later sample cannot discard an already-admitted
gesture's identity. Unknown/indeterminate outcomes keep controls disabled. Only
a fresh, inspectable baseline and an explicit user acknowledgement permit
archiving such an outcome without retrying it. A still-pending operation cannot
be acknowledged. Service evidence is retained independently.

Client state and the exclusive helper lock live under
`$XDG_STATE_HOME/omarchy-minifuse` (standard home fallback), with 0700 directories
and 0600 files. The archive is bounded to 256 records; a full or unwritable store
blocks new admissions. Disable the plugin before archiving resolved records.
Unloading/hot reload closes the connection and preserves the pending reference.

## Presentation and activation

The panel follows `qs.Commons.Color` and `Style` plus `qs.Ui` controls from the
pinned host, including text, spacing and focus states. The normal status slot
has fixed height so confirmations do not move controls. The panel is a managed
floating window; its summon target works even without a visible bar widget.
Escape, Close and normal window dismissal return ownership to the host.

Mix masters are configured levels, not meters. A destination on a different
route bypasses that custom master, so its slider is unavailable. The compact
panel delegates preset comparison/restore and detailed meters to the full app.
Reliable input switch readback is displayed without a panel write path.

The plugin never independently reacts to `control_panel_requested`. The separate
desktop agent may invoke `omarchy-shell shell summon srdiogo.minifuse '{}'` when
physical-button support becomes validated. Opening/reconnecting the plugin is
never treated as a button event. Service and optional agent startup remain
separate user decisions.

## References and compatibility

- [Pinned Omarchy shell contract](https://github.com/omacom/omarchy/blob/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/shell/README.md)
- [Quickshell 0.3.1 process API](https://quickshell.org/docs/v0.3.1/types/Quickshell.Io/Process/)
- [Canonical service protocol](https://github.com/srdiogo/mf-service/blob/main/docs/IPC.md)
- [Canonical continuous-control guarantees](https://github.com/srdiogo/mf-service/blob/main/docs/LIVE_CONTROLS.md)

`host.lock.json` records the tested package/runtime and checksummed source
archive. The selected public source matches the installed host's registry,
scoped shell facade, UI controls, style and shell loader. `contract.lock.json`
pins the producer revision and SHA-256 of the canonical fixtures. These pins
are acceptance references, not a claim that all future versions are compatible.
