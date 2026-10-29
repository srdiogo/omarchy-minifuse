# MiniFuse for Omarchy

Quick hardware mixer controls for the Quickshell-based Omarchy shell. The bar
indicator and floating panel share one client connection to
[mf-service](https://github.com/srdiogo/mf-service). The standalone
[MiniFuse Control application](https://github.com/srdiogo/minifuse-control)
remains a separate project; Omarchy is optional for the platform.

**Status: development preview.** The plugin provides confirmed connection and
input indicators, mix selection, continuous master adjustment, advertised
routes and per-source mute. The full application owns preset comparison and
restore, detailed mixing and signal-meter views. Hardware validation is bounded
to one MiniFuse 4. MF1/MF2 mixer layouts are not inferred.

## Requirements and installation

The tested host is Omarchy 4.0.4-1 with Quickshell 0.3.1 and Qt 6.11.2. Python
3.12–3.14 runs the standard-library socket adapter; it does not require PySide6.
The exact host reference and service contract are recorded in
[host.lock.json](host.lock.json) and [contract.lock.json](contract.lock.json).
Other host versions need acceptance testing.

Install and start the compatible service with the matching administrator-managed
MiniFuse module and session access first. See the coordinated
[transport](https://github.com/srdiogo/mf-cli/releases/tag/preview-2026-10-29)
and [service](https://github.com/srdiogo/mf-service/releases/tag/preview-2026-10-29)
previews. Plugin installation has no package-install or startup hooks.

Review the source, then use the normal host workflow:

```sh
omarchy plugin add https://github.com/srdiogo/omarchy-minifuse.git
omarchy plugin enable srdiogo.minifuse
```

Click **MF** in the bar, focus it and press Enter/Space, or explicitly summon:

```sh
omarchy-shell shell summon srdiogo.minifuse '{}'
```

Device state is read on connection and follows service events. A master gesture
coalesces intermediate movement and preserves the release value. A bypassed
custom mix has its master disabled with an explanation. Source mute uses the
advertised channel operation; no hardware master-mute selector is invented.
INST/+48 V are read-only indicators here; their controls live in the full app.

## Development

```sh
python3 tools/check_project.py
python3 -m unittest discover -s tests -v
python3 tools/check_host.py
python3 tools/run_preview.py
```

The first three commands use contract fixtures and an isolated host configuration;
they do not change device settings. The last command opens the real panel against
the running service, separately from the user's bar, and can control hardware.
Its operation evidence uses a separate persistent preview state directory.

## Documentation

- [Client architecture and host contract](docs/PLUGIN.md)
- [Installation, operation, recovery and removal](docs/INSTALL.md)
- [Implementation and remaining acceptance work](docs/IMPLEMENTATION.md)
- [Validation evidence and limits](docs/VALIDATION.md)
- [Contribution workflow](CONTRIBUTING.md)

The plugin does not subscribe to physical activation events. A separately
optional desktop agent owns that policy and can summon this plugin when the
backend evidence gate is satisfied. Logo-button support remains unavailable.
Firmware, effects, device-storage writers, direct USB and host audio routing
changes are outside scope. This panel controls the MiniFuse hardware mixer;
Omarchy's PipeWire audio widget remains the host volume/application mixer.

New project-owned material is [MIT licensed](LICENSE). This is an independent
community project. Platform research and upstream protocol attribution remain
in [mf-cli](https://github.com/srdiogo/mf-cli).
