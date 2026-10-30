# Installation, operation and removal

Install the matching kernel transport/udev policy through administrator-managed
packaging, then install and run mf-service in the owning login session. This
plugin never installs those prerequisites. The
[backend workspace](https://github.com/srdiogo/mf-service) owns both
`minifuse-driver-dkms` and `mf-service`; the core is compiled into that one
session process. The CLI is not required. Follow its
[fresh-machine installation guide](https://github.com/srdiogo/mf-service/blob/main/docs/INSTALL.md)
and run `minifuse-doctor` before adding the plugin. The upstream v0.2.6 module lacks
the MF4 input-switch and meter extensions used by the wider platform.

Python 3.12–3.14 and the host versions in `host.lock.json` are the supported
test baseline. Review the public repository before adding it:

```sh
omarchy plugin add https://github.com/srdiogo/omarchy-minifuse.git
omarchy plugin enable srdiogo.minifuse
omarchy bar move srdiogo.minifuse --section right
```

The normal installer places the Git checkout under
`~/.config/omarchy/plugins/srdiogo.minifuse/`. It does not run install hooks or
change system packages. The host owns plugin activation and bar placement.
Click the indicator or summon the same panel directly:

```sh
omarchy-shell shell summon srdiogo.minifuse '{}'
```

The session must already expose its private `XDG_RUNTIME_DIR`; the client
connects to `mf-service/control.sock` there and checks the peer UID. Missing,
incompatible or ambiguous devices keep the controls disabled with a reason.
No fake-device mode or raw-USB fallback is available in the installed plugin.

## Optional application and desktop activation

Install the separate MiniFuse Control GUI to use **Open full mixer & presets**.
Its `minifuse-control` launcher must be in the graphical session PATH. A missing
launcher is reported in the panel. Opening the plugin does not launch the GUI.

The separately packaged desktop agent defaults to disabled. Its configured
Omarchy target uses the same summon ID; the plugin does not duplicate that
activation policy. Physical-logo support is still unavailable. Installing or
enabling this panel does not enable service/agent login startup.

## Recovery and evidence

Client identity and operation references are in
`$XDG_STATE_HOME/omarchy-minifuse/client-state.json`; completed or explicitly
acknowledged results are under `operations/`. The standard fallback base is
`~/.local/state`. Files are user-owned and private. Keep unresolved references;
do not delete the identity file to bypass an uncertain result.

After a reconnect the client queries the old operation key. A known terminal
result is archived; a pending result remains pending. For an unknown or
indeterminate outcome, inspect the current mixer state in the full application
and the retained operation reference before choosing **Acknowledge inspected
device state**. This archives the previous identity; it does not repeat a write
or claim that the original pointer position was applied.

If archival storage is full, disable the plugin and move resolved evidence to
a private archive before re-enabling it. A failed or unwritable identity store
prevents new operation admission. Host presets and the service/core operation
journals live in their own locations and are not removed by plugin cleanup.

## Development preview

`python3 tools/run_preview.py` opens the real panel in an independent Quickshell
configuration with the installed host modules. It leaves the current bar intact
and uses `$XDG_STATE_HOME/minifuse-plugin-preview/omarchy-minifuse` for persistent
client evidence. It connects to the real service and can change device settings.
Close the window to stop that preview client. Never delete unresolved preview
references merely to make the next run appear clean.

## Updates and removal

Use `omarchy plugin update srdiogo.minifuse` to review the incoming diff and
fast-forward the checkout. The shell hot-reloads plugin changes. One helper
owns the connection; unload closes it, retains uncertain references and never
replays an accepted operation. The manifest intentionally does not keep an old
service instance mounted across code updates. Some host builds retain compiled
components during structural QML changes; if a reviewed update stays stale after
a rescan, close active controls and use `omarchy restart shell` to reload the
implementation. Pending operation identities survive the helper restart.

```sh
omarchy plugin disable srdiogo.minifuse
omarchy plugin remove srdiogo.minifuse
```

Disabling/removing the plugin leaves the device's current configuration, CLI,
service, full application and user presets usable. Review client evidence
separately before deliberately deleting user-owned state. No packaged Omarchy
file, PipeWire routing or global audio configuration is changed by removal.


## Floating application window

To open the standalone mixer as a floating utility window on Omarchy, copy
`packaging/hyprland/minifuse.lua` to `~/.config/hypr/minifuse.lua`, then add
`require("hypr.minifuse")` after Omarchy defaults in the user `hyprland.lua`.
Run `hyprctl reload` and verify that `hyprctl configerrors` reports no errors.
The rule matches only `io.github.srdiogo.MiniFuseControl`, leaves application
size under user control and centers newly opened windows. Existing windows
need to be floated once if they were opened before the rule was installed.
The panel closes when opening the full mixer so its overlay does not retain
keyboard or pointer ownership. Plugin installation does not apply this user
window policy automatically.
